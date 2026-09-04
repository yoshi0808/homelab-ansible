"""Unit tests for roles/syslog_weekly_digest/filter_plugins/
syslog_weekly_digest.py.

Plain unittest (this repo's established precedent, see
scripts/tests/semaphore_schedules/). Touches no real host and no network.

No IPv4 literal appears in this file's source: sample "IP-shaped" strings
used to exercise the redaction filter are built at runtime via
".".join([...]) so nothing dotted-quad-shaped is present in the committed
text itself (this repo's IPv4 pre-commit check does not scan *.py, but the
same discipline is kept here anyway).

2026-09-04是正(docs/ai/reviews/syslog_weekly_digest/
2026-09-01_003_review_codex.md finding 1・2): 旧
`syslog_weekly_digest_render_errors`は`syslog_weekly_digest_render_message`
へ統合された(error本文だけでなくseries表・no-levelテーブルを含む通知
全体を1関数で組み立て、マスクを行ってから300文字/文字数予算を判定する
ため)。RenderErrorsTestsはRenderMessageTestsへ置き換えた。
"""
import unittest

import _path_setup  # noqa: F401

from syslog_weekly_digest import (
    syslog_weekly_digest_redact_ipv4,
    syslog_weekly_digest_render_message,
)


def _fake_ip(a, b, c, d):
    return ".".join([str(a), str(b), str(c), str(d)])


def _entry(ts, job, host, line):
    return {"ts": ts, "job": job, "host": host, "line": line}


def _row(job, host, level, count):
    return {"job": job, "host": host, "level": level, "count": count}


def _base_data(**overrides):
    """A well-formed, minimal collector output. Tests override only the
    sub-keys they care about.
    """
    data = {
        "window": {"since": "2026-08-25T09:00:00+0900", "until": "2026-09-01T09:00:00+0900", "days": 7},
        "ok": True,
        "series": {"ok": True, "error": None, "rows": [], "total_count": 0, "truncated": False, "limit": 500},
        "error_total": {"ok": True, "error": None, "count": 0},
        "error_entries": {"ok": True, "error": None, "hit_query_limit": False, "query_limit": 300, "entries": []},
    }
    data.update(overrides)
    return data


class RedactIpv4Tests(unittest.TestCase):
    def test_masks_dotted_quad_in_context(self):
        ip = _fake_ip(10, 20, 30, 40)
        line = "Dropped packet from {} to {} port 22".format(ip, _fake_ip(10, 0, 0, 1))
        out = syslog_weekly_digest_redact_ipv4(line)
        self.assertNotIn(ip, out)
        self.assertEqual(out.count("[ip-redacted]"), 2)

    def test_leaves_non_ip_text_alone(self):
        line = "systemd[1]: Starting Daily apt upgrade and clean activities..."
        self.assertEqual(syslog_weekly_digest_redact_ipv4(line), line)

    def test_leaves_short_numeric_sequences_alone(self):
        # Only 2 dot-separated groups -- must not match.
        line = "kernel: cgroup v1.2 mounted"
        self.assertEqual(syslog_weekly_digest_redact_ipv4(line), line)

    def test_known_limitation_version_like_4tuple_is_also_redacted(self):
        # Documented in the filter's module docstring: a 4-part dotted
        # numeric string that is NOT an IP (e.g. a version string) is
        # redacted too, because the detector is a plain dotted-quad regex.
        # This test pins the known false-positive so a future change to the
        # regex does not silently alter behavior without updating the note.
        version = _fake_ip(1, 2, 3, 4)
        line = "libfoo {} loaded".format(version)
        out = syslog_weekly_digest_redact_ipv4(line)
        self.assertNotIn(version, out)
        self.assertIn("[ip-redacted]", out)

    def test_none_passthrough(self):
        self.assertIsNone(syslog_weekly_digest_redact_ipv4(None))


class RenderMessageZeroStateTests(unittest.TestCase):
    def test_zero_series_and_zero_errors(self):
        data = _base_data()
        msg = syslog_weekly_digest_render_message(data)
        self.assertIn("(該当ログなし)", msg)
        self.assertIn("(該当なし)", msg)
        self.assertIn("対象期間中、level=error の行は0件でした。", msg)
        self.assertIn("2026-08-25T09:00:00+0900", msg)
        self.assertIn("直近7日", msg)


class RenderMessageSeriesTests(unittest.TestCase):
    def test_series_rows_rendered(self):
        data = _base_data(
            series={
                "ok": True,
                "error": None,
                "rows": [_row("pve-nodes", "pve2", "warning", 4)],
                "total_count": 1,
                "truncated": False,
                "limit": 500,
            }
        )
        msg = syslog_weekly_digest_render_message(data)
        self.assertIn("job=pve-nodes host=pve2 level=warning : 4", msg)

    def test_series_job_host_masked(self):
        ip = _fake_ip(203, 0, 113, 9)
        data = _base_data(
            series={
                "ok": True,
                "error": None,
                "rows": [_row("network-devices", ip, "(no level label)", 7457)],
                "total_count": 1,
                "truncated": False,
                "limit": 500,
            }
        )
        msg = syslog_weekly_digest_render_message(data)
        self.assertNotIn(ip, msg)
        self.assertIn("[ip-redacted]", msg)

    def test_no_level_subset_extracted_and_masked(self):
        ip = _fake_ip(198, 51, 100, 20)
        rows = [
            _row("pve-nodes", "pve2", "warning", 4),
            _row("network-devices", ip, "(no level label)", 7457),
        ]
        data = _base_data(
            series={"ok": True, "error": None, "rows": rows, "total_count": 2, "truncated": False, "limit": 500}
        )
        msg = syslog_weekly_digest_render_message(data)
        no_level_section = msg.split("levelラベルを持たない系統")[1]
        self.assertIn("job=network-devices", no_level_section)
        self.assertNotIn("warning", no_level_section)
        self.assertNotIn(ip, msg)

    def test_series_truncation_note(self):
        # A generous char_budget isolates the collector-side truncation
        # (series.truncated=True/limit=500) as the ONLY reason -- at the
        # production budget (6000), 500 short rows alone would ALSO trigger
        # filter-side budget truncation (that combined-reason case is
        # covered separately by test_large_series_table_consumes_budget_
        # leaving_less_for_errors), so a larger budget is used here to keep
        # this test's assertion about the "collectorの件数上限" wording
        # focused on a single cause.
        rows = [_row("j{}".format(i), "h{}".format(i), "info", 1) for i in range(500)]
        data = _base_data(
            series={"ok": True, "error": None, "rows": rows, "total_count": 600, "truncated": True, "limit": 500}
        )
        msg = syslog_weekly_digest_render_message(data, char_budget=20000)
        self.assertLessEqual(len(msg), 20000)
        self.assertIn("[TRUNCATED]", msg)
        self.assertIn("600件中500件", msg)
        self.assertIn("上限500", msg)

    def test_series_truncation_note_number_comes_from_collectors_limit_not_a_local_constant(self):
        # Regression for the MAX_SERIES duplication defect (2026-09-04,
        # Coordinator指摘): this function must not carry its own copy of
        # the series row-count cap. The note's number must come from
        # `data.series.limit` (what the collector actually applied), never
        # from a constant baked into this filter. `rows` here is
        # deliberately shorter than `limit` (3 vs 200) so a stale
        # filter-side constant (e.g. a leftover default of 500) or a
        # fallback to len(rows) would both produce the wrong number and
        # this test would catch it.
        rows = [_row("j{}".format(i), "h{}".format(i), "info", 1) for i in range(3)]
        data = _base_data(
            series={"ok": True, "error": None, "rows": rows, "total_count": 250, "truncated": True, "limit": 200}
        )
        msg = syslog_weekly_digest_render_message(data)
        self.assertIn("上限200", msg)
        self.assertNotIn("上限500", msg)
        self.assertNotIn("上限3", msg)

    def test_series_fetch_failure_message_is_masked(self):
        ip = _fake_ip(192, 0, 2, 55)
        data = _base_data(
            series={"ok": False, "error": "Loki request failed near {}".format(ip), "rows": [], "total_count": 0, "truncated": False, "limit": 500}
        )
        msg = syslog_weekly_digest_render_message(data)
        self.assertIn("[取得失敗]", msg)
        self.assertNotIn(ip, msg)


class RenderMessageErrorEntriesTests(unittest.TestCase):
    def test_all_entries_fit_under_budget(self):
        entries = [_entry("2026-09-01T00:00:00+09:00", "pve-nodes", "pve2", "short error {}".format(i)) for i in range(3)]
        data = _base_data(
            error_total={"ok": True, "error": None, "count": 3},
            error_entries={"ok": True, "error": None, "hit_query_limit": False, "query_limit": 300, "entries": entries},
        )
        msg = syslog_weekly_digest_render_message(data, char_budget=6000)
        self.assertNotIn("[TRUNCATED]", msg)
        for e in entries:
            self.assertIn(e["line"], msg)

    def test_final_line_capped_at_300_after_formatting_and_masking(self):
        # A raw body already at 300 chars: once ts/job/host are prefixed,
        # the naive (pre-fix) behavior would exceed 300. The FINAL rendered
        # line (post-format, post-mask) must still be <= 300 (finding 1).
        body = "x" * 300
        entries = [_entry("2026-09-01T00:00:00+09:00", "sophos-fw", "sophos-fw", body)]
        data = _base_data(
            error_total={"ok": True, "error": None, "count": 1},
            error_entries={"ok": True, "error": None, "hit_query_limit": False, "query_limit": 300, "entries": entries},
        )
        msg = syslog_weekly_digest_render_message(data, char_budget=6000)
        error_section = msg.split("error 全文")[1]
        rendered_lines = [l for l in error_section.splitlines() if l.strip()]
        for line in rendered_lines:
            self.assertLessEqual(len(line), 300, msg=repr(line))
        self.assertTrue(any(l.endswith("...") for l in rendered_lines))

    def test_masking_growth_still_respects_300_cap(self):
        # Masking a short IP (len 7) with "[ip-redacted]" (len 13) makes the
        # string LONGER. A line built to land just under 300 chars pre-mask
        # must still be capped to <=300 post-mask.
        ip = _fake_ip(1, 2, 3, 4)
        body = ("a" * 280) + ip  # pre-mask body already close to the cap
        entries = [_entry("2026-09-01T00:00:00+09:00", "j", "h", body)]
        data = _base_data(
            error_total={"ok": True, "error": None, "count": 1},
            error_entries={"ok": True, "error": None, "hit_query_limit": False, "query_limit": 300, "entries": entries},
        )
        msg = syslog_weekly_digest_render_message(data, char_budget=6000)
        error_section = msg.split("error 全文")[1]
        rendered_lines = [l for l in error_section.splitlines() if l.strip()]
        for line in rendered_lines:
            self.assertLessEqual(len(line), 300, msg=repr(line))
        self.assertNotIn(ip, msg)

    def test_job_and_host_masked_in_error_entries(self):
        ip = _fake_ip(198, 51, 100, 33)
        entries = [_entry("2026-09-01T00:00:00+09:00", "network-devices", ip, "deny")]
        data = _base_data(
            error_total={"ok": True, "error": None, "count": 1},
            error_entries={"ok": True, "error": None, "hit_query_limit": False, "query_limit": 300, "entries": entries},
        )
        msg = syslog_weekly_digest_render_message(data)
        self.assertNotIn(ip, msg)
        self.assertIn("[ip-redacted]", msg)

    def test_truncates_when_char_budget_exceeded_and_reports_counts(self):
        entries = [_entry("2026-09-01T00:00:00+09:00", "ubuntu-nodes", "quory", "x" * 30) for _ in range(10)]
        data = _base_data(
            error_total={"ok": True, "error": None, "count": 10},
            error_entries={"ok": True, "error": None, "hit_query_limit": False, "query_limit": 300, "entries": entries},
        )
        # A tiny budget: the header/series/no-level sections consume some
        # of it already, so pass a budget just large enough to admit the
        # fixed sections plus a couple of entry lines.
        msg = syslog_weekly_digest_render_message(data, char_budget=400)
        self.assertIn("[TRUNCATED]", msg)
        self.assertIn("10件中", msg)

    def test_zero_entries_shown_when_remaining_budget_cannot_fit_any(self):
        # 2026-09-04是正2回目(Coordinator指摘への対応): 旧版は「予算が
        # 尽きていても最低1件は表示する」補助則を持っていたが、series・
        # no-levelと予算を奪い合う設計ではこの補助則が本関数自身の
        # `char_budget`超過を引き起こしうる(実際に再現された)。優先順位を
        # 「必ず予算内に収める」側へ倒したため、極端に厳しい予算では
        # 0件表示+正直な注記になる(黙って切るのではなく「2件中0件」と
        # 明示するのでAC3は満たしたまま)。
        entries = [
            _entry("2026-09-01T00:00:00+09:00", "sophos-fw", "sophos-fw", "y" * 250),
            _entry("2026-09-01T00:00:01+09:00", "sophos-fw", "sophos-fw", "second short line"),
        ]
        data = _base_data(
            error_total={"ok": True, "error": None, "count": 2},
            error_entries={"ok": True, "error": None, "hit_query_limit": False, "query_limit": 300, "entries": entries},
        )
        msg = syslog_weekly_digest_render_message(data, char_budget=250)
        self.assertLessEqual(len(msg), 250)
        self.assertIn("[TRUNCATED]", msg)
        self.assertIn("2件中0件", msg)
        self.assertNotIn("y" * 50, msg)

    def test_shows_entries_in_full_when_budget_is_generous(self):
        # Companion to the above: with the production-scale budget (6000),
        # entries the same shape as the tiny-budget case above are shown in
        # full and no truncation note appears -- the tiny-budget behavior
        # above is a genuine budget-pressure response, not a regression in
        # normal operation.
        entries = [
            _entry("2026-09-01T00:00:00+09:00", "sophos-fw", "sophos-fw", "y" * 250),
            _entry("2026-09-01T00:00:01+09:00", "sophos-fw", "sophos-fw", "second short line"),
        ]
        data = _base_data(
            error_total={"ok": True, "error": None, "count": 2},
            error_entries={"ok": True, "error": None, "hit_query_limit": False, "query_limit": 300, "entries": entries},
        )
        msg = syslog_weekly_digest_render_message(data, char_budget=6000)
        self.assertLessEqual(len(msg), 6000)
        self.assertNotIn("[TRUNCATED]", msg)
        self.assertIn("y" * 250, msg)
        self.assertIn("second short line", msg)

    def test_hit_query_limit_note_shown(self):
        entries = [_entry("2026-09-01T00:00:00+09:00", "j", "h", "e{}".format(i)) for i in range(5)]
        data = _base_data(
            error_total={"ok": True, "error": None, "count": 5},
            error_entries={"ok": True, "error": None, "hit_query_limit": True, "query_limit": 300, "entries": entries},
        )
        msg = syslog_weekly_digest_render_message(data)
        self.assertIn("取得件数上限 300", msg)

    def test_query_limit_below_total_count_is_reflected(self):
        # Simulates ERROR_QUERY_LIMIT truncation upstream: fewer raw entries
        # were retrievable than the accurate aggregate total_count.
        entries = [_entry("2026-09-01T00:00:00+09:00", "unifi", "uckg2", "e{}".format(i)) for i in range(5)]
        data = _base_data(
            error_total={"ok": True, "error": None, "count": 9000},
            error_entries={"ok": True, "error": None, "hit_query_limit": True, "query_limit": 300, "entries": entries},
        )
        msg = syslog_weekly_digest_render_message(data, char_budget=6000)
        self.assertIn("9000件中5件", msg)

    def test_truncation_note_names_the_actual_reason_not_a_guessed_budget_claim(self):
        # 2026-09-04是正5回目、Coordinator再現: この分岐(entries自体が
        # total_error_countより少ない)へ来る時点で、collector側の是正
        # (5回目)により理由はhit_query_limitだと保証されている。すべての
        # entriesが予算に余裕をもって収まる(shown_count == len(entries))
        # 場合でも、旧版は「Lokiから取得できた件数(collector側)が総数に
        # 届いていないこと」という曖昧な文言、さらに古い版では「文字数
        # 予算に到達したため」という**誤った**理由を出していた。実際の
        # 理由(query limitの値)を名指しし、budgetを理由に含めないことを
        # 確認する。
        entries = [
            _entry("2026-09-01T00:00:00+09:00", "pve-nodes", "pve2", "short line {}".format(i))
            for i in range(5)
        ]
        data = _base_data(
            error_total={"ok": True, "error": None, "count": 350},
            error_entries={"ok": True, "error": None, "hit_query_limit": True, "query_limit": 300, "entries": entries},
        )
        msg = syslog_weekly_digest_render_message(data, char_budget=6000)
        self.assertIn("[TRUNCATED] error全文は350件中5件のみ表示", msg)
        self.assertIn("取得件数上限300件への到達", msg)
        # The budget was NOT the cause here (all 5 short entries fit
        # trivially) -- the note must not claim it was.
        self.assertNotIn("文字数予算6000字への到達", msg)

    def test_error_query_failure_message_is_masked(self):
        ip = _fake_ip(203, 0, 113, 44)
        data = _base_data(
            error_total={"ok": False, "error": "boom near {}".format(ip), "count": 0},
            error_entries={"ok": True, "error": None, "hit_query_limit": False, "query_limit": 300, "entries": []},
        )
        msg = syslog_weekly_digest_render_message(data)
        self.assertIn("[取得失敗]", msg)
        self.assertNotIn(ip, msg)


class RenderMessageOverallFailureTests(unittest.TestCase):
    def test_overall_not_ok_appends_warning_banner(self):
        data = _base_data(ok=False, series={"ok": False, "error": "boom", "rows": [], "total_count": 0, "truncated": False})
        msg = syslog_weekly_digest_render_message(data)
        self.assertIn("一部のLoki問い合わせに失敗した状態", msg)

    def test_overall_ok_has_no_warning_banner(self):
        data = _base_data(ok=True)
        msg = syslog_weekly_digest_render_message(data)
        self.assertNotIn("一部のLoki問い合わせに失敗した状態", msg)


class RenderMessageBudgetCoversWholeNotificationTests(unittest.TestCase):
    """finding 1 (2.2 third bullet): the char budget must cover the series
    table too, not just the error section.

    2026-09-04是正2回目(再レビューSuggestion 1・Major 1): これらのテストは
    元々「seriesがerrorの残額を減らす」という相対的な効果しか見ておらず、
    最終本文の絶対長が`char_budget`以下であることを直接assertしていな
    かった。この欠陥がまさにCoordinatorの再現(500系列・level無し0件・
    error 0件、予算6000に対し25,543文字・`[TRUNCATED]`無し)を通した。
    以下は`len(message) <= 6000`をproduction値に対して直接assertする。
    """

    def test_large_series_table_consumes_budget_leaving_less_for_errors(self):
        series_rows = [_row("job{}".format(i), "host{}".format(i), "info", i) for i in range(50)]
        error_entries = [_entry("2026-09-01T00:00:00+09:00", "j", "h", "e{}".format(i) * 5) for i in range(50)]
        data = _base_data(
            series={"ok": True, "error": None, "rows": series_rows, "total_count": 50, "truncated": False},
            error_total={"ok": True, "error": None, "count": 50},
            error_entries={"ok": True, "error": None, "hit_query_limit": False, "query_limit": 300, "entries": error_entries},
        )
        small_budget_msg = syslog_weekly_digest_render_message(data, char_budget=800)
        self.assertLessEqual(len(small_budget_msg), 800)
        self.assertIn("[TRUNCATED]", small_budget_msg)
        # With a much larger budget, fewer/no truncation is needed for the
        # same input.
        large_budget_msg = syslog_weekly_digest_render_message(data, char_budget=20000)
        self.assertLessEqual(len(large_budget_msg), 20000)
        self.assertNotIn("[TRUNCATED]", large_budget_msg)

    def test_500_series_zero_no_level_zero_errors_stays_within_production_budget(self):
        # Coordinatorが再現した具体的なシナリオそのもの(2026-09-04):
        # 500系列・level無し0件・error 0件で、是正前は25,543文字/予算6000・
        # `[TRUNCATED]`無しだった。
        rows = [_row("j{}".format(i), "h{}".format(i), "info", 1) for i in range(500)]
        data = _base_data(
            series={"ok": True, "error": None, "rows": rows, "total_count": 500, "truncated": False, "limit": 500}
        )
        msg = syslog_weekly_digest_render_message(data, char_budget=6000)
        self.assertLessEqual(len(msg), 6000)
        self.assertIn("[TRUNCATED]", msg)

    def test_500_series_with_long_labels_stays_within_production_budget(self):
        # 長いjob/hostラベルでも(1行あたりのバイト数が増えても)最終本文が
        # 予算を超えないこと。no-levelテーブルは全series由来なので同時に
        # 大きくなる(2回目是正で見つけた実際のオーバーフロー原因)。
        rows = [
            _row("network-devices", "h{}".format(i) * 5, "(no level label)", i)
            for i in range(500)
        ]
        data = _base_data(
            series={"ok": True, "error": None, "rows": rows, "total_count": 500, "truncated": False, "limit": 500}
        )
        msg = syslog_weekly_digest_render_message(data, char_budget=6000)
        self.assertLessEqual(len(msg), 6000)
        self.assertIn("[TRUNCATED]", msg)

    def test_500_series_plus_50_long_errors_stays_within_production_budget(self):
        # series・no-level・errorのすべてが同時に大きい、最も厳しい組み
        # 合わせ。3セクション合計での予算管理が正しく効くことを確認する。
        rows = [
            _row("network-devices", "h{}".format(i) * 5, "(no level label)", i)
            for i in range(500)
        ]
        entries = [
            _entry("2026-09-01T00:00:00+09:00", "pve-nodes", "pve2", "error line " + "x" * 250)
            for _ in range(50)
        ]
        data = _base_data(
            series={"ok": True, "error": None, "rows": rows, "total_count": 500, "truncated": False, "limit": 500},
            error_total={"ok": True, "error": None, "count": 50},
            error_entries={"ok": True, "error": None, "hit_query_limit": False, "query_limit": 300, "entries": entries},
        )
        msg = syslog_weekly_digest_render_message(data, char_budget=6000)
        self.assertLessEqual(len(msg), 6000)
        self.assertIn("[TRUNCATED] series", msg)
        self.assertIn("[TRUNCATED] error", msg)

    def test_collector_side_and_budget_truncation_combine_within_production_budget(self):
        # series.truncated=True(collector側MAX_SERIES cap)と、この関数
        # 自身のbudget-truncationが両方発生するケース。900件中500件が
        # collectorから渡り、それでも予算6000に対しては表示しきれない。
        rows = [_row("j{}".format(i), "h{}".format(i), "info", 1) for i in range(500)]
        entries = [
            _entry("2026-09-01T00:00:00+09:00", "pve-nodes", "pve2", "error line " + "x" * 250)
            for _ in range(50)
        ]
        data = _base_data(
            series={"ok": True, "error": None, "rows": rows, "total_count": 900, "truncated": True, "limit": 500},
            error_total={"ok": True, "error": None, "count": 50},
            error_entries={"ok": True, "error": None, "hit_query_limit": False, "query_limit": 300, "entries": entries},
        )
        msg = syslog_weekly_digest_render_message(data, char_budget=6000)
        self.assertLessEqual(len(msg), 6000)
        self.assertIn("collectorの件数上限500件", msg)
        self.assertIn("文字数予算6000字", msg)


class RenderMessageTruncationNoteInvariantTests(unittest.TestCase):
    """2026-09-04是正3回目、Coordinator再現(Major 1): 予算には収まって
    いるのに、真の総数(declared_total)より少ないことを示す注記が1つも
    出ないケースがあった(`error_total=21`・`entries=20`・1行258〜260文字
    → 全体5,971〜5,994文字〔予算内〕・表示20/21件・`[TRUNCATED]`無し)。
    旧`_fit_section`+`_add_note`は「候補が全部予算に収まるか」だけで注記の
    要否を決めており、候補自体(entries)がその時点で既にdeclared_total
    (error_total.count)より少ない場合を見ていなかった。

    ここでは「1件でも省略されていれば必ず注記が出る」ことを不変条件として
    直接assertする。Coordinatorが使った総当たり(本文長を150〜300で振り、
    `shown < total` かつ注記が無いケースを探す)をそのまま使う。
    """

    def test_coordinators_exact_repro_now_shows_a_note(self):
        # error_total=21, entries=20 -- entries自体が最初からtotalより
        # 1件少ない(集計クエリと一覧クエリの実行タイミング差、または
        # Loki側のquery limitを想定した典型シナリオ)。
        for line_len in (258, 259, 260):
            entries = [
                _entry("2026-09-01T00:00:00+09:00", "pve-nodes", "pve2", "x" * line_len)
                for _ in range(20)
            ]
            data = _base_data(
                error_total={"ok": True, "error": None, "count": 21},
                error_entries={
                    "ok": True, "error": None, "hit_query_limit": False, "query_limit": 300, "entries": entries,
                },
            )
            msg = syslog_weekly_digest_render_message(data, char_budget=6000)
            self.assertLessEqual(len(msg), 6000, msg="line_len={}".format(line_len))
            shown = msg.count("[pve-nodes/pve2]")
            has_note = "[TRUNCATED]" in msg
            self.assertTrue(
                has_note or shown >= 21,
                msg="line_len={}: shown={} but no truncation note (len={})".format(line_len, shown, len(msg)),
            )

    def test_error_section_boundary_sweep_150_to_300_never_silently_drops_a_note(self):
        # Coordinatorの総当たり方法をそのまま使う: shown < total かつ
        # 注記が無いケースが1件でもあれば不変条件違反として明示的にfailする。
        violations = []
        for line_len in range(150, 301):
            entries = [
                _entry("2026-09-01T00:00:00+09:00", "pve-nodes", "pve2", "x" * line_len)
                for _ in range(20)
            ]
            data = _base_data(
                error_total={"ok": True, "error": None, "count": 21},
                error_entries={
                    "ok": True, "error": None, "hit_query_limit": False, "query_limit": 300, "entries": entries,
                },
            )
            msg = syslog_weekly_digest_render_message(data, char_budget=6000)
            if len(msg) > 6000:
                violations.append(("over_budget", line_len, len(msg)))
                continue
            shown = msg.count("[pve-nodes/pve2]")
            has_note = "[TRUNCATED]" in msg
            if shown < 21 and not has_note:
                violations.append(("missing_note", line_len, shown, len(msg)))
        self.assertEqual(violations, [], msg="invariant violations found: {}".format(violations))

    def test_series_data_known_truncation_always_gets_a_note_even_with_slack(self):
        # series.total_countがrowsより多い(collector側で既に頭打ちに
        # なっている)場合、rows自体は予算に楽に収まるサイズでも注記が
        # 必ず出ることを確認する(series版のCoordinator再現)。
        rows = [_row("j{}".format(i), "h{}".format(i), "info", i) for i in range(5)]
        data = _base_data(
            series={"ok": True, "error": None, "rows": rows, "total_count": 6, "truncated": True, "limit": 5}
        )
        msg = syslog_weekly_digest_render_message(data, char_budget=6000)
        self.assertLessEqual(len(msg), 6000)
        self.assertIn("[TRUNCATED] series", msg)
        self.assertIn("6件中5件", msg)

    def test_downstream_section_is_not_starved_to_silence_by_a_data_heavy_earlier_section(self):
        # 2026-09-04是正3回目で追加で発見した派生ケース: seriesが単独で
        # content_budgetをほぼ使い切るほど大きい場合、旧設計ではno-level/
        # errorセクションが「0件表示・注記も出せない」まま完全に空白に
        # なりえた(fuzzテストで発見)。表示はできなくても、最低限の
        # 注記だけは出ることを確認する。
        rows = [_row("j{}".format(i), "h{}".format(i), "info", i) for i in range(165)]
        entries = [
            _entry("2026-09-01T00:00:00+09:00", "j", "h", "x" * 25) for _ in range(77)
        ]
        data = _base_data(
            series={"ok": True, "error": None, "rows": rows, "total_count": 165, "truncated": False, "limit": 500},
            error_total={"ok": True, "error": None, "count": 78},
            error_entries={
                "ok": True, "error": None, "hit_query_limit": False, "query_limit": 300, "entries": entries,
            },
        )
        msg = syslog_weekly_digest_render_message(data, char_budget=6000)
        self.assertLessEqual(len(msg), 6000)
        self.assertIn("[TRUNCATED] series", msg)
        error_seg = msg.split("--- error 全文")[1]
        self.assertIn("[TRUNCATED] error", error_seg, msg="error section went completely silent: {!r}".format(error_seg))

    def test_series_drags_no_level_down_still_gets_a_note(self):
        # no-levelの候補はseries_rows_shown(series自身の予算切り詰め後の
        # 部分集合)から作られるため、series側の切り詰めがno-level行を
        # 道連れにすることがある。total_no_levelはall_series_rows基準の
        # 真の総数なので、この道連れも検出できることを確認する。
        rows = [_row("a{:03d}".format(i), "h{}".format(i), "warning", i) for i in range(100)]
        rows += [_row("network-devices", "h{}".format(i), "(no level label)", i) for i in range(10)]
        for budget in (2000, 3000, 4000, 4500, 4900):
            data = _base_data(
                series={"ok": True, "error": None, "rows": rows, "total_count": 110, "truncated": False, "limit": 500}
            )
            msg = syslog_weekly_digest_render_message(data, char_budget=budget)
            self.assertLessEqual(len(msg), budget, msg="budget={}".format(budget))
            no_level_seg = msg.split("levelラベルを持たない系統")[1].split("--- error")[0]
            shown_no_level = no_level_seg.count("- job=network-devices")
            has_note = "[TRUNCATED]" in no_level_seg
            self.assertTrue(
                shown_no_level >= 10 or has_note,
                msg="budget={}: no-level section silently short ({} shown, no note)".format(budget, shown_no_level),
            )


if __name__ == "__main__":
    unittest.main()
