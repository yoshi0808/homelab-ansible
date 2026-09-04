"""Integration tests for roles/syslog_weekly_digest/files/
syslog-weekly-digest-collect.py against a local mock Loki HTTP server.

Runs the collector as the real subprocess Ansible would invoke (via
`ansible.builtin.script`), against a throwaway HTTP server bound to
127.0.0.1:3100 (loopback; 127.0.0.1 is explicitly excluded from this
repo's IPv4 pre-commit check, and the collector itself hardcodes
"http://localhost:3100" so the test cannot point it elsewhere). No real
host, no real Loki, no ansible-playbook invocation here (that is covered
separately by run-role-smoke.sh).

Skips (does not fail) if port 3100 is already bound by something else on
the machine running the test, rather than stealing it or silently testing
against a stray real service.

2026-09-04是正(docs/ai/reviews/syslog_weekly_digest/
2026-09-01_003_review_codex.md finding 3): 旧版のsuccess responseは
Lokiの`status`/`data.resultType`を含んでおらず、collectorがそれらを
検証しない欠陥を固定してしまっていた。ここでは正常responseに両方を
含め、さらにHTTP 200のerror envelope・キー欠損・型違い・不正count/value
のケースを追加し、collectorが「本物の0件」と「壊れた/分類できない応答」
を区別してfail-closed(=そのqueryをerrorにする、0やskipへ黙って
フォールバックしない)ことを検証する。
"""
import http.server
import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
import unittest
import urllib.parse

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))
COLLECTOR = os.path.join(
    _REPO_ROOT, "roles", "syslog_weekly_digest", "files", "syslog-weekly-digest-collect.py"
)
_FILTER_PLUGINS_DIR = os.path.join(
    _REPO_ROOT, "roles", "syslog_weekly_digest", "filter_plugins"
)
HOST = "127.0.0.1"
PORT = 3100
# Mirrors the collector's own ERROR_QUERY_LIMIT (2026-09-04是正で300へ
# 変更、helperのQUERY_LIMITと同値)。
ERROR_QUERY_LIMIT = 300


def _load_collector_module():
    # Loaded from the actual file under test (not re-typed as a constant
    # here) so MAX_SERIES below can never drift from what the collector
    # really applies -- the exact duplication failure mode this file's
    # CollectorAndFilterIntegrationTests exists to catch (2026-09-04是正、
    # Coordinator指摘). The filename has hyphens, so a plain `import`
    # cannot reach it; importlib.util loads it by path instead. Importing
    # merely reads module-level constants/functions -- main() only runs
    # under `if __name__ == "__main__"`, so this has no side effects.
    spec = importlib.util.spec_from_file_location(
        "_syslog_weekly_digest_collector_under_test", COLLECTOR
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MAX_SERIES = _load_collector_module().MAX_SERIES


def _recent_ts_ns(seconds_ago=3600):
    """A Loki-style nanosecond timestamp that falls safely inside the
    collector's actual query window (it always queries "now" at run time,
    2026-09-04是正2回目で追加した start/end 範囲チェックの対象になる).
    Fixture timestamps must be relative to wall-clock time, not a fixed
    historical epoch literal, or the collector's new window-bounds check
    (finding 3是正) correctly rejects them as out-of-window.
    """
    return int((time.time() - seconds_ago) * 1e9)


def _port_in_use():
    # SO_REUSEADDR mirrors http.server.HTTPServer's own default
    # (allow_reuse_address = 1), so a socket lingering in TIME_WAIT from a
    # just-closed prior test server is not mistaken for "really busy".
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((HOST, PORT))
        return False
    except OSError:
        return True
    finally:
        s.close()


def _fake_ip(a, b, c, d):
    return ".".join([str(a), str(b), str(c), str(d)])


class _ScenarioHandler(http.server.BaseHTTPRequestHandler):
    """Overridden per-test via a module-level `SCENARIO` dict (set right
    before starting the server in each test) rather than per-instance
    state, because BaseHTTPRequestHandler is instantiated fresh per
    request by the server machinery.
    """

    def log_message(self, fmt, *args):  # silence default stderr logging
        pass

    def do_GET(self):
        scenario = SCENARIO
        parsed = urllib.parse.urlsplit(self.path)
        query_params = urllib.parse.parse_qs(parsed.query)
        logql = query_params.get("query", [""])[0]

        if parsed.path == "/loki/api/v1/query_range":
            body = scenario["query_range_response"]
        elif parsed.path == "/loki/api/v1/query":
            # The two instant queries the collector issues both hit this
            # same endpoint; distinguish them by the decoded LogQL query
            # text (the raw self.path is percent-encoded, so a literal
            # substring check against it would never match).
            if 'level="error"' in logql:
                body = scenario["error_total_response"]
            else:
                body = scenario["series_response"]
        else:
            self.send_response(404)
            self.end_headers()
            return

        status = scenario.get("status", 200)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if scenario.get("malformed_json"):
            self.wfile.write(b"{not json")
        else:
            self.wfile.write(json.dumps(body).encode("utf-8"))


SCENARIO = {}


# --- well-formed envelope builders (include status/resultType, finding 3) --


def _series_envelope(result):
    return {"status": "success", "data": {"resultType": "vector", "result": result}}


def _error_total_envelope(result):
    return {"status": "success", "data": {"resultType": "vector", "result": result}}


def _query_range_envelope(result):
    return {"status": "success", "data": {"resultType": "streams", "result": result}}


def _series_response():
    return _series_envelope(
        [
            {"metric": {"job": "ubuntu-nodes", "host": "quory", "level": "warning"}, "value": [0, "42"]},
            {"metric": {"job": "pve-nodes", "host": "pve2", "level": "error"}, "value": [0, "2"]},
            # No "level" key at all -> "(no level label)".
            {"metric": {"job": "network-devices", "host": "uap-1"}, "value": [0, "7457"]},
        ]
    )


def _error_total_response(count):
    return _error_total_envelope([{"metric": {}, "value": [0, str(count)]}])


def _query_range_response(lines):
    # lines: list of (ts_ns, job, host, text)
    by_stream = {}
    for ts_ns, job, host, text in lines:
        key = (job, host)
        by_stream.setdefault(key, []).append([str(ts_ns), text])
    result = [
        {"stream": {"job": job, "host": host}, "values": values}
        for (job, host), values in by_stream.items()
    ]
    return _query_range_envelope(result)


class _CollectorTestBase(unittest.TestCase):
    """Shared server lifecycle: each test method sets the module-level
    SCENARIO itself and calls _run_with_scenario(), which starts a fresh
    server, runs the collector subprocess, tears the server down, and
    returns the parsed JSON output.
    """

    def setUp(self):
        if _port_in_use():
            self.skipTest("port {} already in use on this machine".format(PORT))

    def _run_with_scenario(self, scenario):
        global SCENARIO
        SCENARIO = scenario
        server = http.server.HTTPServer((HOST, PORT), _ScenarioHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            proc = subprocess.run(
                [sys.executable, COLLECTOR], capture_output=True, text=True, timeout=30
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        return json.loads(proc.stdout)


class CollectorSuccessTests(_CollectorTestBase):
    def _default_scenario(self):
        return {
            "series_response": _series_response(),
            "error_total_response": _error_total_response(2),
            "query_range_response": _query_range_response(
                [
                    (_recent_ts_ns(3600), "pve-nodes", "pve2", "kernel: oops near {}".format(_fake_ip(198, 51, 100, 7))),
                    (_recent_ts_ns(3599), "pve-nodes", "pve2", "kernel: second error line"),
                ]
            ),
        }

    def test_collector_returns_ok_and_expected_shape(self):
        data = self._run_with_scenario(self._default_scenario())

        self.assertTrue(data["ok"])
        self.assertEqual(data["window"]["days"], 7)
        self.assertIn("since", data["window"])
        self.assertIn("until", data["window"])

        self.assertTrue(data["series"]["ok"])
        rows = data["series"]["rows"]
        levels = {r["level"] for r in rows}
        self.assertIn("(no level label)", levels)
        no_level_rows = [r for r in rows if r["level"] == "(no level label)"]
        self.assertEqual(no_level_rows[0]["job"], "network-devices")
        self.assertEqual(no_level_rows[0]["count"], 7457)
        self.assertEqual(data["series"]["total_count"], 3)
        self.assertFalse(data["series"]["truncated"])
        # limit is the cap the collector actually applied (2026-09-04是正,
        # Coordinator指摘: this is the single source of truth the filter
        # reads to build its "上限Nに到達" note -- it must never be
        # duplicated as a separate constant elsewhere).
        self.assertEqual(data["series"]["limit"], MAX_SERIES)

        self.assertTrue(data["error_total"]["ok"])
        self.assertEqual(data["error_total"]["count"], 2)

        self.assertTrue(data["error_entries"]["ok"])
        self.assertEqual(data["error_entries"]["query_limit"], ERROR_QUERY_LIMIT)
        self.assertFalse(data["error_entries"]["hit_query_limit"])
        entries = data["error_entries"]["entries"]
        self.assertEqual(len(entries), 2)
        # Collector does not redact -- that is the playbook/filter's job
        # (check系shellの責務分離). The raw IP passes through untouched here.
        self.assertTrue(any("oops near" in e["line"] for e in entries))
        # Entries are chronologically ascending.
        self.assertLessEqual(entries[0]["ts"], entries[1]["ts"])

    def test_output_is_single_line_valid_json(self):
        global SCENARIO
        SCENARIO = self._default_scenario()
        server = http.server.HTTPServer((HOST, PORT), _ScenarioHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            proc = subprocess.run(
                [sys.executable, COLLECTOR], capture_output=True, text=True, timeout=30
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        lines = [l for l in proc.stdout.splitlines() if l.strip()]
        self.assertEqual(len(lines), 1)
        json.loads(lines[0])  # must not raise

    def test_real_zero_result_is_a_true_zero_not_an_error(self):
        # A well-formed envelope whose `result` is legitimately empty (no
        # matching series at all) must be ok=True with count/rows == 0/[],
        # distinct from a malformed envelope (finding 3).
        scenario = {
            "series_response": _series_envelope([]),
            "error_total_response": _error_total_envelope([]),
            "query_range_response": _query_range_envelope([]),
        }
        data = self._run_with_scenario(scenario)
        self.assertTrue(data["ok"])
        self.assertTrue(data["series"]["ok"])
        self.assertEqual(data["series"]["rows"], [])
        self.assertEqual(data["series"]["total_count"], 0)
        self.assertTrue(data["error_total"]["ok"])
        self.assertEqual(data["error_total"]["count"], 0)
        self.assertTrue(data["error_entries"]["ok"])
        self.assertEqual(data["error_entries"]["entries"], [])

    def test_series_over_max_series_is_truncated_and_reported(self):
        result = [
            {"metric": {"job": "j{}".format(i), "host": "h{}".format(i), "level": "info"}, "value": [0, "1"]}
            for i in range(MAX_SERIES + 1)
        ]
        scenario = {
            "series_response": _series_envelope(result),
            "error_total_response": _error_total_response(0),
            "query_range_response": _query_range_envelope([]),
        }
        data = self._run_with_scenario(scenario)
        self.assertTrue(data["series"]["ok"])
        self.assertEqual(len(data["series"]["rows"]), MAX_SERIES)
        self.assertEqual(data["series"]["total_count"], MAX_SERIES + 1)
        self.assertTrue(data["series"]["truncated"])
        self.assertEqual(data["series"]["limit"], MAX_SERIES)

    def test_error_entries_at_query_limit_sets_hit_query_limit(self):
        lines = [
            (_recent_ts_ns(3600) + i, "pve-nodes", "pve2", "line {}".format(i))
            for i in range(ERROR_QUERY_LIMIT)
        ]
        scenario = {
            "series_response": _series_response(),
            "error_total_response": _error_total_response(ERROR_QUERY_LIMIT),
            "query_range_response": _query_range_response(lines),
        }
        data = self._run_with_scenario(scenario)
        self.assertTrue(data["error_entries"]["ok"])
        self.assertTrue(data["error_entries"]["hit_query_limit"])
        self.assertEqual(len(data["error_entries"]["entries"]), ERROR_QUERY_LIMIT)


class CollectorConnectionFailureTests(_CollectorTestBase):
    """AC4: a failed Loki query must not silently look like success. The
    collector itself must still exit 0 with valid JSON (judgment belongs to
    the Ansible task layer, not the collector) but every sub-result must
    say ok=false with a human-readable, IP-free error string.
    """

    def test_connection_refused_is_reported_as_data_not_a_crash(self):
        # Deliberately do not start any server: connections to
        # localhost:3100 must be refused.
        proc = subprocess.run(
            [sys.executable, COLLECTOR], capture_output=True, text=True, timeout=30
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        data = json.loads(proc.stdout)

        self.assertFalse(data["ok"])
        self.assertFalse(data["series"]["ok"])
        self.assertFalse(data["error_total"]["ok"])
        self.assertFalse(data["error_entries"]["ok"])
        for field in ("series", "error_total", "error_entries"):
            self.assertIsInstance(data[field]["error"], str)
            self.assertGreater(len(data[field]["error"]), 0)
            # No IPv4 literal in the error text (connections are always to
            # the literal hostname "localhost").
            self.assertNotRegex(data[field]["error"], r"(\d{1,3}\.){3}\d{1,3}")


class CollectorMalformedResponseTests(_CollectorTestBase):
    def test_non_json_response_is_reported_as_data_not_a_crash(self):
        data = self._run_with_scenario(
            {
                "series_response": {},
                "error_total_response": {},
                "query_range_response": {},
                "malformed_json": True,
            }
        )
        self.assertFalse(data["ok"])
        self.assertIn("non-JSON", data["series"]["error"])


class CollectorEnvelopeValidationTests(_CollectorTestBase):
    """finding 3: HTTP 200 with a broken/unclassifiable Loki envelope must
    never be coerced into a 0-count success. Each test breaks exactly one
    endpoint's envelope (leaving the other two well-formed) and asserts
    that only that endpoint is reported as failed, with the overall `ok`
    also going false -- never silently defaulted to 0/[]/skip.
    """

    def _good_scenario(self):
        return {
            "series_response": _series_response(),
            "error_total_response": _error_total_response(1),
            "query_range_response": _query_range_response(
                [(_recent_ts_ns(3600), "pve-nodes", "pve2", "one error line")]
            ),
        }

    def test_http_200_error_envelope_is_reported_as_error(self):
        scenario = self._good_scenario()
        error_envelope = {"status": "error", "errorType": "bad_data", "error": "parse error"}
        for key in ("series_response", "error_total_response", "query_range_response"):
            broken = self._good_scenario()
            broken[key] = error_envelope
            data = self._run_with_scenario(broken)
            self.assertFalse(data["ok"], msg="{} should fail overall ok".format(key))

        # series only
        broken = self._good_scenario()
        broken["series_response"] = error_envelope
        data = self._run_with_scenario(broken)
        self.assertFalse(data["series"]["ok"])
        self.assertIn("success", data["series"]["error"])
        self.assertTrue(data["error_total"]["ok"])
        self.assertTrue(data["error_entries"]["ok"])

    def test_missing_data_key_is_reported_as_error(self):
        broken = self._good_scenario()
        broken["series_response"] = {"status": "success"}
        data = self._run_with_scenario(broken)
        self.assertFalse(data["series"]["ok"])
        self.assertIn("data", data["series"]["error"])
        self.assertEqual(data["series"]["rows"], [])

    def test_wrong_result_type_is_reported_as_error(self):
        broken = self._good_scenario()
        broken["error_total_response"] = {
            "status": "success",
            "data": {"resultType": "matrix", "result": []},
        }
        data = self._run_with_scenario(broken)
        self.assertFalse(data["error_total"]["ok"])
        self.assertIn("resultType", data["error_total"]["error"])
        self.assertEqual(data["error_total"]["count"], 0)

    def test_non_list_result_is_reported_as_error(self):
        broken = self._good_scenario()
        broken["query_range_response"] = {
            "status": "success",
            "data": {"resultType": "streams", "result": "oops"},
        }
        data = self._run_with_scenario(broken)
        self.assertFalse(data["error_entries"]["ok"])
        self.assertEqual(data["error_entries"]["entries"], [])

    def test_non_numeric_count_is_reported_as_error_not_zero(self):
        broken = self._good_scenario()
        broken["error_total_response"] = _error_total_envelope(
            [{"metric": {}, "value": [0, "not-a-number"]}]
        )
        data = self._run_with_scenario(broken)
        self.assertFalse(data["error_total"]["ok"])
        # Must not silently become 0 -- that would be indistinguishable
        # from a real zero (AC5).
        self.assertEqual(data["error_total"]["count"], 0)
        self.assertIn("numeric", data["error_total"]["error"])

    def test_missing_metric_field_is_reported_as_error(self):
        broken = self._good_scenario()
        broken["series_response"] = _series_envelope([{"value": [0, "5"]}])  # no "metric" key
        data = self._run_with_scenario(broken)
        self.assertFalse(data["series"]["ok"])
        self.assertIn("metric", data["series"]["error"])

    def test_error_total_with_multiple_series_is_reported_as_error(self):
        # sum(...) must collapse to at most one series; more than one is a
        # shape violation the collector cannot silently pick a winner from.
        broken = self._good_scenario()
        broken["error_total_response"] = _error_total_envelope(
            [{"metric": {}, "value": [0, "1"]}, {"metric": {}, "value": [0, "2"]}]
        )
        data = self._run_with_scenario(broken)
        self.assertFalse(data["error_total"]["ok"])

    def test_query_range_stream_missing_labels_is_reported_as_error(self):
        broken = self._good_scenario()
        broken["query_range_response"] = _query_range_envelope(
            [{"values": [["1735689600000000000", "line"]]}]  # no "stream" key
        )
        data = self._run_with_scenario(broken)
        self.assertFalse(data["error_entries"]["ok"])
        self.assertIn("stream", data["error_entries"]["error"])

    def test_query_range_non_numeric_timestamp_is_reported_as_error(self):
        broken = self._good_scenario()
        broken["query_range_response"] = _query_range_envelope(
            [{"stream": {"job": "j", "host": "h"}, "values": [["not-a-timestamp", "line"]]}]
        )
        data = self._run_with_scenario(broken)
        self.assertFalse(data["error_entries"]["ok"])
        self.assertEqual(data["error_entries"]["entries"], [])

    def test_query_range_non_string_line_is_reported_as_error(self):
        broken = self._good_scenario()
        broken["query_range_response"] = _query_range_envelope(
            [{"stream": {"job": "j", "host": "h"}, "values": [["1735689600000000000", 12345]]}]
        )
        data = self._run_with_scenario(broken)
        self.assertFalse(data["error_entries"]["ok"])

    def test_status_missing_entirely_is_reported_as_error(self):
        broken = self._good_scenario()
        broken["series_response"] = {"data": {"resultType": "vector", "result": []}}
        data = self._run_with_scenario(broken)
        self.assertFalse(data["series"]["ok"])

    # --- error_total(集計クエリ)とerror_entries(一覧クエリ)が食い違う
    # ときのfail-closed検証。
    #
    # 4回目是正: 「観測した行数の方が総数より多い」向き(total <
    # len(entries))は黙って0件/過小報告へ倒さず、当該query群の不整合と
    # してfail-closedにした。
    #
    # 5回目是正(Coordinator再現・Coordinatorの前回指示の訂正): 逆向き
    # (total > len(entries))を無条件に正常としていた4回目是正時の判断は
    # 誤りだった。`hit_query_limit=false`のまま`total > len(entries)`が
    # 通ると、ERROR_QUERY_LIMITでは説明できず、文字数予算による省略も
    # collectorより後段のfilterで起きるためcollector段の理由にはならない
    # ——理由不明の欠落がそのまま正常として通り、しかもfilter側の注記が
    # 「文字数予算に到達したため」という**誤った理由**を出していた
    # (黙ってはいないが、間違った理由を告げていた)。collector段で観測
    # できる正当な理由は`hit_query_limit`だけであり、`total >
    # len(entries)`は`hit_query_limit`が真の場合だけ通す。

    def test_total_zero_but_entries_observed_is_reported_as_inconsistent(self):
        # Coordinatorの再現そのもの: error_total.count=0 なのに
        # error_entries.entries に1件観測されている。「0件でした」と
        # 言い切ってはならない。
        broken = self._good_scenario()
        broken["error_total_response"] = _error_total_response(0)
        broken["query_range_response"] = _query_range_response(
            [(_recent_ts_ns(3600), "pve-nodes", "pve2", "observed error line")]
        )
        data = self._run_with_scenario(broken)
        self.assertFalse(data["ok"])
        self.assertFalse(data["error_total"]["ok"])
        self.assertFalse(data["error_entries"]["ok"])
        self.assertIn("disagree", data["error_total"]["error"])
        self.assertIn("disagree", data["error_entries"]["error"])

    def test_total_less_than_entries_count_is_reported_as_inconsistent(self):
        # total=1・entries=3件のような、totalが観測件数より小さい場合も
        # 同様に不整合として扱う(Coordinatorが挙げた2例目)。
        broken = self._good_scenario()
        broken["error_total_response"] = _error_total_response(1)
        broken["query_range_response"] = _query_range_response(
            [
                (_recent_ts_ns(3600), "pve-nodes", "pve2", "line 1"),
                (_recent_ts_ns(3599), "pve-nodes", "pve2", "line 2"),
                (_recent_ts_ns(3598), "pve-nodes", "pve2", "line 3"),
            ]
        )
        data = self._run_with_scenario(broken)
        self.assertFalse(data["ok"])
        self.assertFalse(data["error_total"]["ok"])
        self.assertFalse(data["error_entries"]["ok"])

    def test_total_greater_than_entries_without_hit_query_limit_is_inconsistent(self):
        # 2026-09-04是正5回目、Coordinatorの再現そのもの: total=5・
        # entries=1・hit_query_limit=false。ERROR_QUERY_LIMIT(300)には
        # 遠く及ばずhit_query_limitが立たないため、4件の欠落を説明する
        # 観測可能な理由が無い。4回目是正時点ではこれを正常としていたが、
        # 5回目是正で不整合としてfail-closedにするよう訂正した。
        broken = self._good_scenario()
        broken["error_total_response"] = _error_total_response(5)
        broken["query_range_response"] = _query_range_response(
            [(_recent_ts_ns(3600), "pve-nodes", "pve2", "only one retrieved")]
        )
        data = self._run_with_scenario(broken)
        self.assertFalse(data["ok"])
        self.assertFalse(data["error_total"]["ok"])
        self.assertFalse(data["error_entries"]["ok"])
        self.assertFalse(data["error_entries"]["hit_query_limit"])
        self.assertIn("disagree", data["error_total"]["error"])
        self.assertIn("hit_query_limit", data["error_total"]["error"])

    def test_total_greater_than_entries_with_hit_query_limit_remains_ok(self):
        # 逆向き(total > len(entries))のうち、hit_query_limitが真の場合
        # (entriesがERROR_QUERY_LIMITで頭打ちになった場合)だけは観測
        # できる正当な理由があるため通す。
        broken = self._good_scenario()
        broken["error_total_response"] = _error_total_response(350)
        lines = [
            (_recent_ts_ns(3600) + i, "pve-nodes", "pve2", "line {}".format(i))
            for i in range(ERROR_QUERY_LIMIT)
        ]
        broken["query_range_response"] = _query_range_response(lines)
        data = self._run_with_scenario(broken)
        self.assertTrue(data["ok"])
        self.assertTrue(data["error_total"]["ok"])
        self.assertTrue(data["error_entries"]["ok"])
        self.assertTrue(data["error_entries"]["hit_query_limit"])
        self.assertEqual(data["error_total"]["count"], 350)
        self.assertEqual(len(data["error_entries"]["entries"]), ERROR_QUERY_LIMIT)

    def test_total_equal_to_entries_count_remains_ok(self):
        # 完全一致(total == len(entries))は正常な0件/N件の一致であり、
        # 不整合検知の対象外であること。
        broken = self._good_scenario()
        broken["error_total_response"] = _error_total_response(0)
        broken["query_range_response"] = _query_range_response([])
        data = self._run_with_scenario(broken)
        self.assertTrue(data["ok"])
        self.assertTrue(data["error_total"]["ok"])
        self.assertTrue(data["error_entries"]["ok"])
        self.assertEqual(data["error_total"]["count"], 0)
        self.assertEqual(data["error_entries"]["entries"], [])

    # --- 2026-09-04是正2回目: 再レビューがCoordinator側で再現・指摘した
    # 追加のshape違反(finding 3再レビュー)。collector全体(subprocess)が
    # クラッシュせず有効なJSONで終わり、当該queryだけがok=falseになる
    # ことを確認する。

    def test_non_object_vector_item_in_series_is_reported_as_error_not_a_crash(self):
        # Coordinatorが`result: [null]`で`AttributeError`を再現した箇所。
        broken = self._good_scenario()
        broken["series_response"] = _series_envelope([None])
        data = self._run_with_scenario(broken)  # must not raise / hang
        self.assertFalse(data["series"]["ok"])
        self.assertIn("not an object", data["series"]["error"])

    def test_non_object_vector_item_in_error_total_is_reported_as_error_not_a_crash(self):
        broken = self._good_scenario()
        broken["error_total_response"] = _error_total_envelope([None])
        data = self._run_with_scenario(broken)
        self.assertFalse(data["error_total"]["ok"])
        self.assertIn("not an object", data["error_total"]["error"])

    def test_huge_exponent_count_is_reported_as_error_not_a_crash(self):
        # 巨大な指数表記は float() では inf になり例外にならないが、旧実装
        # では続く int(inf) が OverflowError で未処理落ちしていた。
        broken = self._good_scenario()
        broken["error_total_response"] = _error_total_envelope(
            [{"metric": {}, "value": [0, "1e400"]}]
        )
        data = self._run_with_scenario(broken)
        self.assertFalse(data["error_total"]["ok"])
        self.assertEqual(data["error_total"]["count"], 0)
        self.assertIn("finite", data["error_total"]["error"])

    def test_negative_count_is_reported_as_error_not_accepted(self):
        broken = self._good_scenario()
        broken["series_response"] = _series_envelope(
            [{"metric": {"job": "j", "host": "h", "level": "info"}, "value": [0, "-5"]}]
        )
        data = self._run_with_scenario(broken)
        self.assertFalse(data["series"]["ok"])
        self.assertIn("negative", data["series"]["error"])

    def test_non_integer_count_is_reported_as_error_not_truncated(self):
        broken = self._good_scenario()
        broken["series_response"] = _series_envelope(
            [{"metric": {"job": "j", "host": "h", "level": "info"}, "value": [0, "3.7"]}]
        )
        data = self._run_with_scenario(broken)
        self.assertFalse(data["series"]["ok"])
        self.assertIn("integer", data["series"]["error"])

    def test_non_string_count_value_is_reported_as_error(self):
        broken = self._good_scenario()
        broken["error_total_response"] = _error_total_envelope([{"metric": {}, "value": [0, 5]}])
        data = self._run_with_scenario(broken)
        self.assertFalse(data["error_total"]["ok"])
        self.assertIn("not a string", data["error_total"]["error"])

    def test_mixed_type_job_labels_are_reported_as_error_not_a_crash(self):
        # 2026-09-04是正3回目、Coordinator再現(Major 2): metric.jobが
        # int/strで混在すると、`rows.sort(key=lambda r: (r["job"], ...))`が
        # `TypeError: '<' not supported between instances of 'int' and
        # 'str'`で未処理落ちすることを確認した。「labelのstring型は
        # str.format()では落ちない」という2回目是正時の判断は、sort()と
        # いう別の経路を見ていなかったための誤りだった。この経路は
        # 個別のisinstance検査(job/host/level)で塞いだ。
        broken = self._good_scenario()
        broken["series_response"] = _series_envelope(
            [
                {"metric": {"job": 123, "host": "h1", "level": "info"}, "value": [0, "1"]},
                {"metric": {"job": "str-job", "host": "h2", "level": "info"}, "value": [0, "2"]},
            ]
        )
        data = self._run_with_scenario(broken)  # must not raise / hang
        self.assertFalse(data["series"]["ok"])
        self.assertIn("not a string", data["series"]["error"])

    def test_mixed_type_host_and_level_labels_are_reported_as_error_not_a_crash(self):
        # 同上、host/levelラベルでも同型の混在型sort crashを個別に確認する。
        broken_host = self._good_scenario()
        broken_host["series_response"] = _series_envelope(
            [
                {"metric": {"job": "j1", "host": 1, "level": "info"}, "value": [0, "1"]},
                {"metric": {"job": "j2", "host": "h2", "level": "info"}, "value": [0, "2"]},
            ]
        )
        data = self._run_with_scenario(broken_host)
        self.assertFalse(data["series"]["ok"])
        self.assertIn("not a string", data["series"]["error"])

        broken_level = self._good_scenario()
        broken_level["series_response"] = _series_envelope(
            [
                {"metric": {"job": "j1", "host": "h1", "level": 1}, "value": [0, "1"]},
                {"metric": {"job": "j2", "host": "h2", "level": "info"}, "value": [0, "2"]},
            ]
        )
        data = self._run_with_scenario(broken_level)
        self.assertFalse(data["series"]["ok"])
        self.assertIn("not a string", data["series"]["error"])

    def _scenario_with_error_total_and_query_limit_hit(self, total_raw):
        # 2026-09-04是正5回目: 5回目是正で`error_total > len(entries)`は
        # `hit_query_limit`が真の場合しか通らなくなった(理由が観測できない
        # 食い違いはfail-closedになる)。error_totalの値そのもの
        # (`_parse_count`の丸め検証)を単体でテストするには、entries側を
        # ちょうどERROR_QUERY_LIMIT件用意してhit_query_limit=Trueにし、
        # 「entriesが上限に頭打ちになったので総数の方が大きいのは当然」
        # という整合した状態を作る必要がある。
        scenario = self._good_scenario()
        scenario["error_total_response"] = _error_total_envelope([{"metric": {}, "value": [0, total_raw]}])
        lines = [
            (_recent_ts_ns(3600) + i, "pve-nodes", "pve2", "line {}".format(i))
            for i in range(ERROR_QUERY_LIMIT)
        ]
        scenario["query_range_response"] = _query_range_response(lines)
        return scenario

    def test_large_count_is_parsed_exactly_not_rounded_via_float(self):
        # 2026-09-04是正3回目、Coordinator再現(Major 2): 旧`_parse_count`は
        # `int(float(raw))`経由だったため、2**53を超える整数(例:
        # 9007199254740993)がfloatの53bit仮数部で9007199254740992へ
        # 丸められていた。クラッシュはしないが「表示している数字が実際と
        # 違う」欠陥であり、MAX_SERIES二重化と同種の性質を持つ。
        big = 9007199254740993  # 2**53 + 1, not exactly representable as float
        broken = self._scenario_with_error_total_and_query_limit_hit(str(big))
        data = self._run_with_scenario(broken)
        self.assertTrue(data["error_total"]["ok"])
        self.assertEqual(data["error_total"]["count"], big)

    def test_decimal_and_exponential_large_counts_are_parsed_exactly(self):
        # 2026-09-04是正4回目、Coordinator再現(Minor): 3回目是正は
        # プレーン整数リテラル("9007199254740993")の丸めは解消したが、
        # 小数点・指数表記("9007199254740993.0" /
        # "9.007199254740993e15")を伴う同じ整数値は、float()を経由する
        # 分類パスで依然として9007199254740992へ丸められていた。
        big = 9007199254740993  # 2**53 + 1
        for raw in ("9007199254740993.0", "9.007199254740993e15"):
            with self.subTest(raw=raw):
                broken = self._scenario_with_error_total_and_query_limit_hit(raw)
                data = self._run_with_scenario(broken)
                self.assertTrue(data["error_total"]["ok"], msg=raw)
                self.assertEqual(data["error_total"]["count"], big, msg=raw)

    def test_out_of_range_timestamp_is_reported_as_error_not_a_crash(self):
        # `int(ts_ns_raw)`自体は巨大な数値文字列でも例外にならないが、旧
        # 実装では後段の`datetime.fromtimestamp()`が`OverflowError`で
        # 未処理落ちすることをCoordinatorが確認した。
        broken = self._good_scenario()
        broken["query_range_response"] = _query_range_envelope(
            [{"stream": {"job": "j", "host": "h"}, "values": [["100000000000000000000000000000", "line"]]}]
        )
        data = self._run_with_scenario(broken)  # must not raise / hang
        self.assertFalse(data["error_entries"]["ok"])
        self.assertIn("outside the requested query window", data["error_entries"]["error"])

    def test_moderately_out_of_window_timestamp_is_reported_as_error(self):
        # プラットフォームのtime_t範囲には収まるが、要求したquery window
        # からは明らかに外れている値(1970年付近)。OverflowErrorにはならな
        # いが、実在範囲チェックで拒否されるべき。
        broken = self._good_scenario()
        broken["query_range_response"] = _query_range_envelope(
            [{"stream": {"job": "j", "host": "h"}, "values": [["1000000000", "line"]]}]
        )
        data = self._run_with_scenario(broken)
        self.assertFalse(data["error_entries"]["ok"])
        self.assertIn("outside the requested query window", data["error_entries"]["error"])


class CollectorAndFilterIntegrationTests(_CollectorTestBase):
    """2026-09-04是正、Coordinator指摘への直接の回帰テスト: MAX_SERIESが
    collector(実際に切り捨てる側)とfilter(通知文の数字を出す側)の2箇所
    に複製されていると、片方だけ変更されたとき「上限Nに到達」という文言
    がNの部分だけ嘘をつく。ここでは実際のcollector subprocessの出力を、
    実際のfilter関数(`syslog_weekly_digest_render_message`)へそのまま
    渡し、本文の数字がcollectorの実際の`MAX_SERIES`(このファイルの先頭で
    collectorから直接importした値であり、テスト側で再定義した数値では
    ない)と一致することを確認する。
    """

    def test_series_truncation_note_number_matches_collectors_actual_max_series(self):
        result = [
            {"metric": {"job": "j{}".format(i), "host": "h{}".format(i), "level": "info"}, "value": [0, "1"]}
            for i in range(MAX_SERIES + 7)
        ]
        scenario = {
            "series_response": _series_envelope(result),
            "error_total_response": _error_total_response(0),
            "query_range_response": _query_range_envelope([]),
        }
        data = self._run_with_scenario(scenario)
        self.assertTrue(data["series"]["truncated"])
        self.assertEqual(data["series"]["limit"], MAX_SERIES)

        if _FILTER_PLUGINS_DIR not in sys.path:
            sys.path.insert(0, _FILTER_PLUGINS_DIR)
        from syslog_weekly_digest import syslog_weekly_digest_render_message

        # A generous char_budget isolates the collector-side MAX_SERIES cap
        # as the only truncation cause (at the production budget of 6000,
        # 500+ short rows would ALSO trigger filter-side budget truncation
        # on top of it -- that combined-reason case is covered by
        # test_filters.py's own budget tests). What this test exists to
        # prove is narrower and more important: the NUMBER in the note
        # traces back to the collector's real MAX_SERIES end to end.
        msg = syslog_weekly_digest_render_message(data, char_budget=50000)
        self.assertIn("collectorの件数上限{}件".format(MAX_SERIES), msg)
        self.assertIn("{}件中{}件".format(MAX_SERIES + 7, MAX_SERIES), msg)


if __name__ == "__main__":
    unittest.main()
