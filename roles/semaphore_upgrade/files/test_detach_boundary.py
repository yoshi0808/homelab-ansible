"""Local SQLite and mocked service/Slack fixtures; no host operations."""
import importlib.util
import json
import os
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml

spec = importlib.util.spec_from_file_location("detached", Path(__file__).with_name("semaphore-upgrade-detached.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "db"
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("create table task(id integer, status text)")
            conn.execute("insert into task values(1, 'running')")
            conn.commit()
        (self.root / "semaphore.bin").write_bytes(b"old")
        (self.root / "binary").write_bytes(b"new")
        self.cfg = dict(mode="upgrade", origin_job_id="1", job_wait_timeout=2,
                        db=str(self.db), backup_dir=str(self.root), binary=str(self.root / "binary"),
                        current_binary_sha256=mod.sha256(self.root / "semaphore.bin"),
                        current_version="2.19.8", target_version="2.19.12",
                        current_edition="pro", target_edition="community", skip_notifications=True,
                        skip_reading_path_check=True,
                        result_file=str(self.root / "result.json"), webhook_file=str(self.root / "webhook"),
                        notification_suppress_marker=str(self.root / "marker"))

    def test_terminal_then_other_job_finishes(self):
        events = []
        def advance(_seconds):
            with closing(sqlite3.connect(self.db)) as conn:
                if not events:
                    conn.execute("update task set status='success' where id=1")
                    conn.execute("insert into task values(2, 'running')")
                else:
                    conn.execute("update task set status='success' where id=2")
                conn.commit()
            events.append("poll")
        with patch.object(mod.time, "sleep", side_effect=advance):
            mod.wait_for_jobs(self.cfg)
        self.assertEqual(len(events), 2)

    def test_timeout_restores_without_stop_or_post(self):
        for status in ("running", "success"):
            with self.subTest(status=status):
                with closing(sqlite3.connect(self.db)) as conn:
                    conn.execute("update task set status=? where id=1", (status,))
                    conn.execute("insert or replace into task values(2, 'running')")
                    conn.commit()
                config = self.root / "config.json"
                config.write_text(json.dumps(self.cfg))
                with patch.object(sys, "argv", ["detached", str(config)]), \
                     patch.object(mod.time, "monotonic", side_effect=[0, 3]), \
                     patch.object(mod, "stop") as stop, patch.object(mod, "notify") as notify:
                    self.assertEqual(mod.main(), 0)
                stop.assert_not_called()
                notify.assert_not_called()
                self.assertEqual((self.root / "binary").read_bytes(), b"old")
                result = json.loads((self.root / "result.json").read_text())
                self.assertEqual(result["status"], "aborted")
                self.assertTrue(result["binary_restored"])
                self.assertIn("安全に引き返し", result["notification"]["message"])

    def test_missing_origin_is_not_terminal(self):
        self.cfg["origin_job_id"] = "99"
        with patch.object(mod.time, "monotonic", side_effect=[0, 3]):
            with self.assertRaises(mod.BoundaryTimeout):
                mod.wait_for_jobs(self.cfg)

    def test_api_observes_origin_and_all_jobs(self):
        self.cfg["skip_reading_path_check"] = False
        self.cfg["query_command"] = "/query"
        self.cfg["query_user"] = "consumer"
        replies = [
            mod.subprocess.CompletedProcess([], 0, "1|Upgrade|playbooks/semaphore_upgrade.yml|running|start|\n", ""),
            mod.subprocess.CompletedProcess([], 0, "1|Upgrade|playbooks/semaphore_upgrade.yml|running|start\n", ""),
            mod.subprocess.CompletedProcess([], 0, "1|Upgrade|playbooks/semaphore_upgrade.yml|success|start|end\n", ""),
            mod.subprocess.CompletedProcess([], 0, "", ""),
        ]
        with patch.object(mod, "run", side_effect=replies) as query, patch.object(mod.time, "sleep"):
            mod.wait_for_jobs(self.cfg)
        self.assertEqual(query.call_args_list[0].args[0][1:3], ["task-time", "1"])
        self.assertEqual(query.call_args_list[1].args[0][1:3], ["running", "200"])

    def test_actual_include_order_defines_capture_inputs(self):
        tasks_dir = Path(__file__).parents[1] / "tasks"
        main = yaml.safe_load((tasks_dir / "main.yml").read_text())
        upgrade = yaml.safe_load((tasks_dir / "upgrade.yml").read_text())
        rollback = yaml.safe_load((tasks_dir / "rollback.yml").read_text())

        self.assertFalse(any(task.get("ansible.builtin.include_tasks") == "capture_origin.yml" for task in main))

        def index(tasks, name):
            return next(i for i, task in enumerate(tasks) if task.get("name") == name)

        upgrade_capture = index(upgrade, "Identify launching job before package installation")
        self.assertLess(index(upgrade, "Determine whether the consumer reading path is available"), upgrade_capture)
        self.assertLess(index(upgrade, "Discover non-owner consumer identity from token ACL"), upgrade_capture)
        self.assertLess(index(upgrade, "Record the explicitly skipped consumer reading path"), upgrade_capture)
        upgrade_vars = upgrade[upgrade_capture]["vars"]
        self.assertIn("semaphore_upgrade_origin_reading_path_available", upgrade_vars)
        self.assertIn("semaphore_upgrade_origin_query_user", upgrade_vars)

        rollback_capture = index(rollback, "Identify launching rollback job")
        self.assertLess(index(rollback, "Determine whether the rollback reading path is available"), rollback_capture)
        self.assertLess(index(rollback, "Rediscover rollback consumer identity from current token ACL"), rollback_capture)
        rollback_vars = rollback[rollback_capture]["vars"]
        self.assertIn("semaphore_upgrade_origin_reading_path_available", rollback_vars)
        self.assertIn("semaphore_upgrade_origin_query_user", rollback_vars)

        preflight = upgrade[index(upgrade, "Require no other running job and at most this one upgrade job")]
        fail_msg = preflight["ansible.builtin.assert"]["fail_msg"]
        self.assertIn("semaphore_upgrade_other_job_lines", fail_msg)
        self.assertIn("semaphore_upgrade_self_job_lines", fail_msg)
        self.assertIn("immediately after rollback", fail_msg)
        self.assertIn("Semaphore UI", fail_msg)

    def test_non_timeout_failure_reports_observed_safe_state(self):
        self.cfg["db"] = str(self.root / "missing" / "db")
        config = self.root / "bad-db-config.json"
        config.write_text(json.dumps(self.cfg))
        with patch.object(sys, "argv", ["detached", str(config)]), \
             patch.object(mod, "stop") as stop, patch.object(mod, "notify") as notify:
            self.assertEqual(mod.main(), 1)
        stop.assert_not_called()
        notify.assert_not_called()
        result = json.loads((self.root / "result.json").read_text())
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["binary_restored"])
        self.assertFalse(result["service_stop_attempted"])
        self.assertIn("安全に引き返し", result["notification"]["message"])

    def test_rollback_timeout_does_not_touch_binary(self):
        self.cfg.update(mode="rollback", origin_job_id="1")
        before = (self.root / "binary").read_bytes()
        config = self.root / "rollback-config.json"
        config.write_text(json.dumps(self.cfg))
        with patch.object(sys, "argv", ["detached", str(config)]), \
             patch.object(mod.time, "monotonic", side_effect=[0, 3]), \
             patch.object(mod, "stop") as stop:
            self.assertEqual(mod.main(), 0)
        stop.assert_not_called()
        self.assertEqual((self.root / "binary").read_bytes(), before)

    def test_rollback_non_timeout_failure_reports_observed_safe_state(self):
        self.cfg.update(mode="rollback", db=str(self.root / "missing" / "db"))
        before = (self.root / "binary").read_bytes()
        config = self.root / "rollback-bad-db-config.json"
        config.write_text(json.dumps(self.cfg))
        with patch.object(sys, "argv", ["detached", str(config)]), \
             patch.object(mod, "stop") as stop, patch.object(mod, "notify") as notify:
            self.assertEqual(mod.main(), 1)
        stop.assert_not_called()
        notify.assert_not_called()
        self.assertEqual((self.root / "binary").read_bytes(), before)
        result = json.loads((self.root / "result.json").read_text())
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["binary_unchanged"])
        self.assertFalse(result["service_stop_attempted"])
        self.assertIn("安全に引き返し", result["notification"]["message"])

    def test_notification_shapes(self):
        title, text = mod.notification_text(self.cfg, {"status": "success"})
        self.assertIn("成功", title)
        self.assertIn("2.19.8 → 2.19.12", text)
        self.assertIn("pro → community", text)
        self.assertIn("+09:00", text)
        self.assertNotIn("dpkg", text)
        self.assertNotIn("result=", text)
        self.assertIn("変更バージョン", text)
        _, text = mod.notification_text(self.cfg, {"status": "failed", "rollback": "success",
             "dpkg_bookkeeping": mod.DPKG_BOOKKEEPING_NOTE, "error": "x" * 10000})
        self.assertIn("復帰先: 2.19.8 (pro)", text)
        self.assertIn("dpkg -V", text)
        self.assertLessEqual(len(text), 2900)
        rollback_cfg = dict(self.cfg, mode="rollback", report_from_version="2.19.12",
                            report_from_edition="community",
                            ledger_restored_at="2026-09-06T01:00:00+09:00")
        _, text = mod.notification_text(rollback_cfg, {"status": "success"})
        self.assertIn("変更バージョン: 2.19.12 → 2.19.8", text)
        self.assertIn("変更エディション: community → pro", text)
        self.assertIn("ジョブ台帳: 退避時点", text)
        self.assertIn("これ以降のジョブ記録は失われ", text)
        self.assertIn("running として復活", text)
        self.assertIn("次回版上げの preflight", text)
        self.assertIn("Semaphore UI", text)

    def test_upgrade_failure_reports_timestamp_of_actually_restored_db(self):
        snapshot = self.root / "semaphore-final.db"
        snapshot.write_bytes(b"snapshot")
        snapshot_epoch = 1788624000
        os.utime(snapshot, (snapshot_epoch, snapshot_epoch))
        self.cfg.update(
            service="semaphore.service",
            db_uid=os.getuid(),
            db_gid=os.getgid(),
            db_mode="0600",
            baseline={},
            target_binary_sha256="target-hash",
        )
        config = self.root / "upgrade-auto-rollback.json"
        config.write_text(json.dumps(self.cfg))
        with patch.object(sys, "argv", ["detached", str(config)]), \
             patch.object(mod, "wait_for_jobs"), \
             patch.object(mod, "stop"), \
             patch.object(mod, "sqlite_backup"), \
             patch.object(mod.os, "chown"), \
             patch.object(mod, "start_and_verify", side_effect=[RuntimeError("verify failed"), None]):
            self.assertEqual(mod.main(), 1)
        result = json.loads((self.root / "result.json").read_text())
        self.assertEqual(result["rollback"], "success")
        self.assertEqual((self.root / "db").read_bytes(), b"snapshot")
        self.assertIn("2026-09-06T01:00:00+09:00", result["notification"]["message"])
        self.assertIn("これ以降のジョブ記録は失われ", result["notification"]["message"])

    def test_rollback_main_reports_observed_source(self):
        pre_rollback = self.root / "pre-rollback"
        pre_rollback.mkdir()
        self.cfg.update(
            mode="rollback",
            pre_rollback_dir=str(pre_rollback),
            current_binary_sha256="old-hash",
            target_binary_sha256="target-hash",
        )
        config = self.root / "rollback-main-config.json"
        config.write_text(json.dumps(self.cfg))
        with patch.object(sys, "argv", ["detached", str(config)]), \
             patch.object(mod, "wait_for_jobs"), \
             patch.object(mod, "version", return_value="2.19.12"), \
             patch.object(mod, "sha256", return_value="target-hash"), \
             patch.object(mod, "counts", return_value={}), \
             patch.object(mod, "sqlite_backup"), \
             patch.object(mod, "restore"):
            self.assertEqual(mod.main(), 0)
        result = json.loads((self.root / "result.json").read_text())
        message = result["notification"]["message"]
        self.assertIn("変更バージョン: 2.19.12 → 2.19.8", message)
        self.assertIn("変更エディション: community → pro", message)


if __name__ == "__main__":
    unittest.main()
