"""Regression coverage for the R2-restored connection-target check
(semaphore_activation_gate_removal案件、独立レビュー `2026-08-24_003_
review.md` Finding 1 / `2026-08-24_004_review.md` High 1 /
`2026-08-24_005_review.md` High 1 / requirement R2 改訂).

The removed activation gate bundled 5 conditions (explicit per-run
permission, closed-world, zero unmanaged, no schedule-set drift, and
canonical-URL match) into one evaluation. Only the canonical-URL
condition survives the removal, restructured as two small, independent
functions:

- `semaphore_schedules_would_newly_activate(before_active, desired_
  active)`: whether writing `desired_active` would newly turn a schedule
  on, given the value observed *immediately before this specific write*.
  **This replaces an earlier `semaphore_schedules_activation_targets
  (diff_result)` (2026-08-24, removed the same day it was added)** that
  computed the "would activate" list once from a diff-time snapshot --
  independent review reproduced, against real ansible-core, a schedule
  whose diff-time snapshot showed only a `cron_format` change (so it
  was never flagged as an activation target) getting deactivated via the
  UI *between* the diff and the write, and then reactivated by the write
  itself, because the write always sends the catalog's `active` value.
  The new signature takes only two primitives -- no diff_result, no
  schedule identity. **This is a call-site convention (the live task
  files pass a fresh-GET value), not something the signature itself
  enforces** -- an earlier version of this docstring overstated this as
  "structural" prevention; independent review (`2026-08-24_005_review.md`
  Suggestion 1) corrected that.
  **2026-08-24再々追補(same review, High 1):** the function itself did
  not validate that either argument was actually a `bool` -- a fresh-GET
  `active` value that came back as the non-bool string `"false"` passed
  through Python's bare truthiness (`bool("false")` is `True`) and was
  silently read as "already active", letting a non-canonical connection's
  write through. Fixed to require real `bool` (or `None` for
  `before_active`, meaning "does not exist yet") and to treat anything
  else as "cannot prove this is not an activating write" (`True`) --
  fail-closed, never a guess.
- `semaphore_schedules_url_matches_canonical`: whether the connection
  used matches the catalog's canonical production URL -- pure string
  normalization, no network, no timing dependency (the two inputs are
  both static configuration for the duration of a single run).

Both are exercised directly here (not just read) per the instruction that
prompted this file: expression-level bugs (e.g. the 2026-08-23 `regex_
replace` backreference defect elsewhere in this repo, the 2026-08-24
diff-time-snapshot race, and the 2026-08-24 truthiness-on-non-bool defect,
both reproduced against earlier versions of this same check) do not show
up from reading code, only from running it.
"""

import unittest

import _path_setup  # noqa: F401

from semaphore_schedules import (
    semaphore_schedules_url_matches_canonical,
    semaphore_schedules_would_newly_activate,
)

_CANONICAL = 'https://quory.example.internal:3000/api'


class WouldNewlyActivateTests(unittest.TestCase):
    def test_not_active_to_active_is_newly_activating(self):
        self.assertTrue(semaphore_schedules_would_newly_activate(False, True))

    def test_already_active_to_active_is_not_newly_activating(self):
        self.assertFalse(semaphore_schedules_would_newly_activate(True, True))

    def test_active_to_inactive_is_not_newly_activating(self):
        self.assertFalse(semaphore_schedules_would_newly_activate(True, False))

    def test_inactive_to_inactive_is_not_newly_activating(self):
        self.assertFalse(semaphore_schedules_would_newly_activate(False, False))

    def test_a_schedule_that_does_not_exist_yet_counts_as_not_active(self):
        """新規schedule向け -- 'before' に相当する値が無い(存在しない)
        ときは None を渡すと「未有効」として扱う(before_active=Falseと
        同じ結果になる、R2の規約)。
        """
        self.assertTrue(semaphore_schedules_would_newly_activate(None, True))
        self.assertFalse(semaphore_schedules_would_newly_activate(None, False))

    def test_regression_the_2026_08_24_diff_snapshot_race_would_now_be_caught(self):
        """独立レビューが`2026-08-24_004_review.md`で実Ansibleにより再現
        した経路: diff時点ではactive:true(そのためcronのみが差分に見
        える)が、実際のPUT直前のfresh GETではactive:falseになっていた
        ケース。旧`semaphore_schedules_activation_targets`はdiff時点の
        fieldsしか見ないため検出できなかった -- ここではfresh GETで
        観測した値(実bool)を渡す限り正しく検出される。
        """
        fresh_active_at_write_time = False  # UIが diff の後に false へ変えた
        desired_active = True  # カタログは変わらず active:true
        self.assertTrue(
            semaphore_schedules_would_newly_activate(fresh_active_at_write_time, desired_active)
        )


class WouldNewlyActivateNonBoolFailsClosedTests(unittest.TestCase):
    """`2026-08-24_005_review.md` High 1: 実Ansibleで、fresh GETの
    `active`が非bool(文字列 `"false"`)のとき旧実装が`would_activate=
    false`を返し、非canonical接続先へのPUTを許してしまうことが再現され
    た。ここでは「曖昧さの無い真偽値でなければ、有効化するかもしれない
    側(=True)へ倒す」という修正後の契約を、代表的な非bool形状すべてに
    ついて固定する。Pythonのbare truthinessへは一切通さない
    (`bool("false")`は`True`になるため、既存値と紛らわしい形が特に
    危険 -- そのケースを名指しでテストする)。
    """

    def test_before_active_string_false_does_not_pass_as_inactive(self):
        """報告された実際のバグそのもの: 文字列 "false" は
        `bool("false")`が`True`になるため、旧実装は「既にactive」と
        誤判定した。修正後は非boolとして扱われ、有効化するかもしれない
        側(True)へ倒れる。
        """
        self.assertTrue(semaphore_schedules_would_newly_activate("false", True))

    def test_before_active_string_true_is_also_not_a_bool(self):
        self.assertTrue(semaphore_schedules_would_newly_activate("true", True))

    def test_before_active_empty_string_is_not_a_bool(self):
        self.assertTrue(semaphore_schedules_would_newly_activate("", True))

    def test_before_active_int_zero_is_not_a_bool(self):
        self.assertTrue(semaphore_schedules_would_newly_activate(0, True))

    def test_before_active_int_one_is_not_a_bool(self):
        self.assertTrue(semaphore_schedules_would_newly_activate(1, True))

    def test_before_active_dict_is_not_a_bool(self):
        self.assertTrue(semaphore_schedules_would_newly_activate({}, True))

    def test_before_active_list_is_not_a_bool(self):
        self.assertTrue(semaphore_schedules_would_newly_activate([], True))

    def test_desired_active_string_true_is_not_a_bool(self):
        """desired_active側が非boolのときも、値に関わらず「有効化する
        かもしれない」側(True)へ倒す -- desired_active自体が本来
        preflightのcatalog検査(⑤)で弾かれるはずの形だが、この関数は
        呼び出し元の事前検証を信用せず自分でも守る(防御的プログラミング)。
        """
        self.assertTrue(semaphore_schedules_would_newly_activate(False, "true"))

    def test_desired_active_string_false_is_not_a_bool(self):
        self.assertTrue(semaphore_schedules_would_newly_activate(False, "false"))

    def test_desired_active_int_is_not_a_bool(self):
        self.assertTrue(semaphore_schedules_would_newly_activate(False, 1))

    def test_desired_active_none_is_not_a_bool(self):
        self.assertTrue(semaphore_schedules_would_newly_activate(False, None))

    def test_desired_active_dict_is_not_a_bool(self):
        self.assertTrue(semaphore_schedules_would_newly_activate(False, {}))

    def test_a_real_bool_false_before_active_is_still_the_unambiguous_safe_case(self):
        """非boolを拒否する修正が、正当なbool falseまで巻き込んで
        fail-closedにしていないことの確認(過剰検出の回帰防止)。
        """
        self.assertTrue(semaphore_schedules_would_newly_activate(False, True))
        self.assertFalse(semaphore_schedules_would_newly_activate(True, True))


class UrlMatchesCanonicalTests(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(semaphore_schedules_url_matches_canonical(_CANONICAL, _CANONICAL))

    def test_trailing_slash_notation_difference_still_matches(self):
        self.assertTrue(
            semaphore_schedules_url_matches_canonical(_CANONICAL + '/', _CANONICAL)
        )

    def test_scheme_and_host_case_difference_still_matches(self):
        upper = 'HTTPS://Quory.Example.Internal:3000/api'
        self.assertTrue(semaphore_schedules_url_matches_canonical(upper, _CANONICAL))

    def test_alias_hostname_for_the_same_server_does_not_match(self):
        """旧R15と同じ判断: allowlist型であり、別名DNSは吸収しない。"""
        alias = 'https://quory-alias.example.internal:3000/api'
        self.assertFalse(semaphore_schedules_url_matches_canonical(alias, _CANONICAL))

    def test_different_port_does_not_match(self):
        self.assertFalse(
            semaphore_schedules_url_matches_canonical(
                'https://quory.example.internal:3001/api', _CANONICAL,
            )
        )

    def test_unrelated_url_does_not_match(self):
        self.assertFalse(
            semaphore_schedules_url_matches_canonical(
                'https://ansy.example.internal:3000/api', _CANONICAL,
            )
        )

    def test_empty_canonical_never_matches(self):
        """canonical側が空/未設定なら、どんなURLでも一致しない(fail-closed
        側へ倒す -- 「一致するときだけ許可」の裏返し)。
        """
        self.assertFalse(semaphore_schedules_url_matches_canonical(_CANONICAL, ''))
        self.assertFalse(semaphore_schedules_url_matches_canonical(_CANONICAL, None))


if __name__ == "__main__":
    unittest.main()
