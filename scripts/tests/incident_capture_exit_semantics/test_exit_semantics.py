"""Offline integration tests for incident-capture-collector.py.

Each test runs the real ``main()`` against temporary spool, state, and bundle
directories. Semaphore and investigate calls are replaced in-process, so no
host, network endpoint, Ansible execution, or Slack notification is touched.
"""

import contextlib
import glob
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from _path_setup import COLLECTOR_PATH, _REPO_ROOT, collector


class CollectorExitSemanticsTests(unittest.TestCase):
    def _record(self, status):
        return {
            "record_version": 1,
            "written_at": "2026-09-21T09:00:13+09:00",
            "controller": "fixture",
            "play_name": "fixture play",
            "play_host": "fixture-host",
            "slack_channel": "patches",
            "slack_status": status,
            "slack_title": "fixture",
            "slack_message": "fixture",
            "skip_notifications": False,
            "check_mode": False,
        }

    def _run(self, records, base_snapshot=None, host_snapshot=None, break_move=False):
        with tempfile.TemporaryDirectory() as root:
            spool_dir = os.path.join(root, "spool")
            bundle_dir = os.path.join(root, "bundles")
            state_dir = os.path.join(root, "state")
            os.makedirs(spool_dir)
            for index, record in enumerate(records):
                with open(os.path.join(spool_dir, "{}.json".format(index)), "w", encoding="utf-8") as handle:
                    json.dump(record, handle)
            cfg = {
                "spool_dir": spool_dir,
                "bundle_dir": bundle_dir,
                "state_dir": state_dir,
                "semaphore_query_bin": "/fixture/semaphore-query",
                "semaphore_query_timeout_s": 1,
                "recent_failed_batch": 10,
                "spool_correlation_tolerance_s": 90,
                "base_snapshot_targets": [],
                "failure_snapshot_ops": {},
                "investigate_bin_template": "/fixture/investigate-{host}",
                "ssh_snapshot_timeout_s": 1,
                "retention_days": 7,
            }
            config_path = os.path.join(root, "config.json")
            with open(config_path, "w", encoding="utf-8") as handle:
                json.dump(cfg, handle)

            def query(_bin_path, _timeout, operation, *_args):
                self.assertEqual(operation, "recent-failed")
                return 0, "", ""

            snapshots = host_snapshot or ([], None)
            base_results = base_snapshot or []
            patches = [
                mock.patch.object(collector, "run_semaphore_query", side_effect=query),
                mock.patch.object(collector, "collect_base_snapshot", return_value=base_results),
                mock.patch.object(collector, "collect_host_snapshot", return_value=snapshots),
                mock.patch.object(collector, "apply_retention"),
                mock.patch.object(sys, "argv", [COLLECTOR_PATH, config_path]),
            ]
            if break_move:
                patches.append(mock.patch.object(collector.shutil, "move", side_effect=OSError("fixture move failure")))
            with contextlib.ExitStack() as stack:
                for patch in patches:
                    stack.enter_context(patch)
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    exit_code = collector.main()
            summaries = []
            for path in glob.glob(os.path.join(bundle_dir, "spool-*", "summary.json")):
                with open(path, encoding="utf-8") as handle:
                    summaries.append(json.load(handle))
            return exit_code, stderr.getvalue(), summaries, bundle_dir

    def test_info_uncorrelated_is_note_and_exits_ok_without_journal(self):
        exit_code, stderr, summaries, _ = self._run([self._record("info")])
        self.assertEqual(exit_code, collector.EXIT_OK)
        self.assertEqual(stderr, "")
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["collection_errors"], [])
        note = summaries[0]["correlation_notes"][0]
        self.assertIn("no correlated Semaphore job", note["what"])
        self.assertIn("90s", note["why"])

    def test_warning_uncorrelated_is_note_and_exits_ok(self):
        exit_code, stderr, summaries, _ = self._run([self._record("warning")])
        self.assertEqual(exit_code, collector.EXIT_OK)
        self.assertEqual(stderr, "")
        self.assertEqual(len(summaries[0]["correlation_notes"]), 1)

    def test_error_and_critical_remain_collection_errors(self):
        for status in ("error", "critical"):
            with self.subTest(status=status):
                exit_code, _stderr, summaries, _ = self._run([self._record(status)])
                self.assertEqual(exit_code, collector.EXIT_COLLECTION_ERRORS)
                self.assertEqual(len(summaries[0]["collection_errors"]), 1)
                self.assertNotIn("correlation_notes", summaries[0])

    def test_mixed_info_and_error_only_records_error_as_collection_error(self):
        exit_code, _stderr, summaries, _ = self._run([self._record("info"), self._record("error")])
        self.assertEqual(exit_code, collector.EXIT_COLLECTION_ERRORS)
        self.assertEqual(sum(len(summary["collection_errors"]) for summary in summaries), 1)
        self.assertEqual(sum(len(summary.get("correlation_notes", [])) for summary in summaries), 1)

    def test_unknown_missing_and_non_string_statuses_fail_closed(self):
        cases = [("unknown",), (42,), ([],), ({},)]
        for (status,) in cases:
            with self.subTest(status=repr(status)):
                record = self._record(status)
                exit_code, _stderr, summaries, _ = self._run([record])
                self.assertEqual(exit_code, collector.EXIT_COLLECTION_ERRORS)
                self.assertEqual(len(summaries[0]["collection_errors"]), 1)
        missing = self._record("info")
        del missing["slack_status"]
        exit_code, _stderr, _summaries, _ = self._run([missing])
        self.assertEqual(exit_code, collector.EXIT_COLLECTION_ERRORS)

    def test_bundle_level_error_after_info_note_remains_exit_two(self):
        no_ops_error = {"what": "no named investigate operations available", "why": "fixture"}
        exit_code, _stderr, summaries, _ = self._run(
            [self._record("info")], host_snapshot=(None, no_ops_error)
        )
        self.assertEqual(exit_code, collector.EXIT_COLLECTION_ERRORS)
        self.assertEqual(len(summaries[0]["correlation_notes"]), 1)
        self.assertEqual(summaries[0]["collection_errors"], [no_ops_error])

    def test_missing_wrapper_after_info_note_remains_exit_two(self):
        missing_wrapper = {
            "host": "fixture-host",
            "op": "status",
            "missing_binary": True,
            "error": "fixture wrapper missing",
        }
        exit_code, _stderr, summaries, _ = self._run(
            [self._record("info")], base_snapshot=[missing_wrapper]
        )
        self.assertEqual(exit_code, collector.EXIT_COLLECTION_ERRORS)
        self.assertEqual(len(summaries[0]["correlation_notes"]), 1)
        self.assertEqual(
            summaries[0]["collection_errors"][0]["what"],
            "investigate wrapper missing for fixture-host status",
        )

    def test_reject_move_failure_remains_collection_error(self):
        exit_code, _stderr, summaries, _ = self._run([{"broken": True}], break_move=True)
        self.assertEqual(exit_code, collector.EXIT_COLLECTION_ERRORS)
        self.assertEqual(summaries, [])

    def test_internal_exception_exits_three(self):
        missing_config = os.path.join(tempfile.gettempdir(), "incident-capture-fixture-missing-config.json")
        if os.path.exists(missing_config):
            os.remove(missing_config)
        process = subprocess.run(
            [sys.executable, COLLECTOR_PATH, missing_config], capture_output=True, text=True, timeout=10
        )
        self.assertEqual(process.returncode, collector.EXIT_INTERNAL_ERROR)
        self.assertIn("unexpected internal error", process.stderr)

    def test_exit_constants_and_service_unit_are_unchanged(self):
        self.assertEqual((collector.EXIT_OK, collector.EXIT_COLLECTION_ERRORS, collector.EXIT_INTERNAL_ERROR), (0, 2, 3))
        unit_path = os.path.join(_REPO_ROOT, "roles", "incident_capture", "templates", "incident-capture.service.j2")
        with open(unit_path, encoding="utf-8") as handle:
            unit = handle.read()
        self.assertIn("flock -n -E 75", unit)
        self.assertNotIn("SuccessExitStatus", unit)

    def test_semaphore_bundle_shape_is_unchanged(self):
        def query(_bin_path, _timeout, operation, _task_id):
            if operation == "task-time":
                return 0, "99|template|playbook.yml|error|2026-09-21T00:00:00Z|2026-09-21T00:01:00Z\n", ""
            if operation == "task-output":
                return 0, "fixture output\n", ""
            self.assertIn(operation, ("task-errors", "task-hosts"))
            return 0, "", ""

        cfg = {"semaphore_query_bin": "/fixture/query", "semaphore_query_timeout_s": 1}
        row = {"id": 99, "template": "template", "playbook": "playbook.yml", "status": "error", "start_raw": ""}
        with mock.patch.object(collector, "run_semaphore_query", side_effect=query):
            summary, raw_logs = collector.build_semaphore_bundle(cfg, row)
        self.assertEqual(summary["bundle_id"], "semaphore-99")
        self.assertEqual(summary["source"], "semaphore")
        self.assertEqual(set(summary), {"bundle_id", "source", "semaphore", "spool_records", "snapshot", "collection_errors"})
        self.assertNotIn("correlation_notes", summary)
        self.assertEqual(raw_logs, {"semaphore-log.log": "fixture output\n"})


if __name__ == "__main__":
    unittest.main()
