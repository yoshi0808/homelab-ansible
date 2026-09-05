#!/usr/bin/env python3
"""Finish a Semaphore self-upgrade outside semaphore.service's cgroup."""

import hashlib
from datetime import datetime, timedelta, timezone
from contextlib import closing
import json
import os
import pathlib
import pwd
import signal
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request

DEFAULT_WEBHOOK_FILE = "/run/semaphore-upgrade-webhook"
DEFAULT_SUPPRESS_MARKER = "/run/semaphore-upgrade-notifications-suppressed"
DEFAULT_RESULT_FILE = "/var/log/semaphore-upgrade-result.json"
DPKG_BOOKKEEPING_NOTE = (
    "バイナリを直接復元したため、dpkg -V の不一致は想定内です。"
    "次回の版上げでパッケージを再インストールすると解消します。"
)


class BoundaryTimeout(RuntimeError):
    """The service must remain running; only the installed binary is undone."""


def wait_for_jobs(cfg):
    """Observe origin and all jobs through API, or SQLite after explicit skip."""
    timeout = int(cfg["job_wait_timeout"])
    if not 0 < timeout <= 600:
        raise ValueError("job_wait_timeout must be between 1 and 600 seconds")
    deadline = time.monotonic() + timeout
    origin = cfg["origin_job_id"]
    while True:
        terminal = True
        if cfg.get("skip_reading_path_check", False):
            with closing(sqlite3.connect(f"file:{cfg['db']}?mode=ro", uri=True, timeout=1)) as conn:
                if origin:
                    row = conn.execute("select status from task where id = ?", (int(origin),)).fetchone()
                    terminal = row is not None and row[0] in ("success", "error", "stopped")
                active = conn.execute(
                    "select count(*) from task where status is null or status not in ('success', 'error', 'stopped')"
                ).fetchone()[0]
        else:
            if origin:
                observed = run(
                    [cfg["query_command"], "task-time", str(origin)],
                    user=cfg["query_user"], check=False,
                )
                fields = observed.stdout.strip().split("|")
                if observed.returncode != 0 or len(fields) != 6 or fields[0] != str(origin):
                    raise RuntimeError("起動元ジョブの状態を読み取れません")
                terminal = fields[3] in ("success", "error", "stopped")
            running = run(
                [cfg["query_command"], "running", "200"],
                user=cfg["query_user"], check=False,
            )
            if running.returncode != 0:
                raise RuntimeError("走行中ジョブを読み取れません")
            lines = running.stdout.splitlines()
            if any(len(line.split("|")) != 5 for line in lines):
                raise RuntimeError("走行中ジョブの応答形式が不正です")
            active = len(lines)
        if terminal and active == 0:
            return
        if time.monotonic() >= deadline:
            raise BoundaryTimeout("起動元ジョブの終端を確認できません" if not terminal else "他のジョブが終了しません")
        time.sleep(min(1, max(0, deadline - time.monotonic())))


def undo_install_without_stop(cfg):
    """Replace the pathname atomically; never overwrite a running executable."""
    source = pathlib.Path(cfg["backup_dir"]) / "semaphore.bin"
    target = pathlib.Path(cfg["binary"])
    temporary = target.with_name(target.name + ".upgrade-restore")
    if sha256(source) != cfg["current_binary_sha256"]:
        raise RuntimeError("退避バイナリのsha256が一致しません")
    try:
        shutil.copy2(source, temporary)
        source_stat = source.stat()
        os.chown(temporary, source_stat.st_uid, source_stat.st_gid)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    if sha256(target) != cfg["current_binary_sha256"]:
        raise RuntimeError("中止時のバイナリ復元を確認できません")


def notification_text(cfg, result):
    def field(value):
        return str(value).replace('\n', ' ')[:250]

    status = result["status"]
    icon, label = {"success": ("✅", "成功"), "aborted": ("⚠️", "中止")}.get(status, ("❌", "失敗"))
    title = f"{icon} [Semaphore] {label}"
    rollback = cfg.get("mode") == "rollback"
    old = cfg.get("target_version" if rollback else "current_version", "不明")
    new = cfg.get("current_version" if rollback else "target_version", "不明")
    old_ed = cfg.get("target_edition" if rollback else "current_edition", "不明")
    old = cfg.get("report_from_version", old)
    old_ed = cfg.get("report_from_edition", old_ed)
    new_ed = cfg.get("current_edition" if rollback else "target_edition", "不明")
    transition = "予定" if status == "aborted" or (status == "failed" and not result.get("rollback")) else "変更"
    if status == "failed" and result.get("rollback"):
        transition = "版上げ試行"
    lines = [f"ホスト: {field(os.uname().nodename)}", f"結果: {label}（{'ロールバック' if rollback else '版上げ'}）",
             f"{transition}バージョン: {field(old)} → {field(new)}", f"{transition}エディション: {field(old_ed)} → {field(new_ed)}",
             f"時刻: {datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')}",
             f"退避先: {field(cfg.get('backup_dir', '不明'))}"]
    if (result.get("binary_restored") or result.get("binary_unchanged")) and not result.get("service_stop_attempted"):
        lines.append("安全に引き返しました。Semaphoreの停止・再起動は行っていません。稼働中の版は変更していません。")
        lines.append(
            "install前のバイナリへ復元しました。"
            if result.get("binary_restored") else "バイナリ変更は行っていません。"
        )
    if result.get("rollback") or (rollback and status == "success"):
        lines.append(f"ロールバック: {field(result.get('rollback', 'success'))} / 復帰先: {field(cfg.get('current_version', '不明'))} ({field(cfg.get('current_edition', '不明'))})")
    if result.get("rollback") == "success" or (rollback and status == "success"):
        restore_point = cfg.get("ledger_restore_point")
        if not restore_point:
            restore_point = pathlib.Path(cfg.get("backup_dir", "不明")).name.split("-from-", 1)[0]
        lines.append(
            f"ジョブ台帳: 退避時点（{field(restore_point)}）へ巻き戻しました。"
            "これ以降のジョブ記録は失われ、退避時に走行中だった行が running として復活します。"
        )
        lines.append(
            "復活した走行中行は次回版上げの preflight を止める場合があります。"
            "Semaphore UI で該当行を stopped にしてから再実行してください。"
        )
    for key, label in (("error", "理由"), ("rollback_error", "復元エラー"), ("recovery_error", "安全網エラー")):
        if key in result:
            lines.append(f"{label}: {field(result[key])}")
    if "dpkg_bookkeeping" in result:
        lines.append(DPKG_BOOKKEEPING_NOTE)
    return title, '\n'.join(lines)[:2900]


def interrupted(signum, _frame):
    raise RuntimeError(f"terminated by signal {signum}")


def run(argv, *, user=None, check=True):
    if user:
        argv = ["runuser", "-u", user, "--", *argv]
    return subprocess.run(argv, check=check, text=True, capture_output=True)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def version(binary):
    value = run([binary, "version"]).stdout.strip().split("-", 1)[0]
    if not value or any(not part.isdigit() for part in value.split(".")):
        raise RuntimeError(f"unreadable Semaphore version: {value!r}")
    return value


def counts(db_path):
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        return {
            "templates": conn.execute("select count(*) from project__template").fetchone()[0],
            "schedules": conn.execute("select count(*) from project__schedule").fetchone()[0],
            "active_schedules": conn.execute(
                "select count(*) from project__schedule where active=1"
            ).fetchone()[0],
        }


def sqlite_backup(source, destination):
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)


def http_ok(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return 200 <= response.status < 400
    except Exception:
        return False


def journal_markers_ok(service, target_version, since):
    output = run(
        ["journalctl", "-u", service, "--since", since, "--no-pager"],
        check=False,
    ).stdout
    return f"Semaphore {target_version}-" in output and "Server is running" in output


def consumer_query_ok(command, user, service_owner, expected_keys):
    if pwd.getpwnam(user).pw_uid == 0 or user == service_owner:
        raise RuntimeError("query identity is privileged or owns Semaphore service")
    result = run([command, "template-list", "1"], user=user, check=False)
    lines = result.stdout.splitlines()
    if result.returncode != 0 or len(lines) != 1:
        raise RuntimeError("consumer-identity Semaphore query failed")
    observed = json.loads(lines[0])
    if not isinstance(observed, dict):
        raise RuntimeError("consumer-identity Semaphore query is not an object")
    if sorted(observed) != sorted(expected_keys):
        raise RuntimeError("consumer-identity Semaphore query shape changed")


def stop(service):
    run(["systemctl", "stop", service])
    if run(["systemctl", "is-active", service], check=False).stdout.strip() != "inactive":
        raise RuntimeError("Semaphore did not become inactive")


def start_and_verify(cfg, expected_version, expected_hash, expected_counts):
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    run(["systemctl", "start", cfg["service"]])
    deadline = time.monotonic() + int(cfg["health_timeout"])
    stable_since = None
    while time.monotonic() < deadline:
        active = run(
            ["systemctl", "is-active", cfg["service"]], check=False
        ).stdout.strip() == "active"
        healthy = http_ok(cfg["http_url"])
        if active and healthy:
            stable_since = stable_since or time.monotonic()
            if time.monotonic() - stable_since >= int(cfg["stability_seconds"]):
                break
        else:
            stable_since = None
        time.sleep(5)
    else:
        raise RuntimeError("service did not remain active and HTTP-healthy")
    if version(cfg["binary"]) != expected_version:
        raise RuntimeError("unexpected Semaphore version after restart")
    if sha256(cfg["binary"]) != expected_hash:
        raise RuntimeError("unexpected Semaphore edition/binary after restart")
    if counts(cfg["db"]) != expected_counts:
        raise RuntimeError("templates/schedules/active_schedules baseline changed")
    if not journal_markers_ok(cfg["service"], expected_version, started):
        raise RuntimeError("journal lacks target version or 'Server is running'")
    if not cfg.get("skip_reading_path_check", False):
        consumer_query_ok(
            cfg["query_command"],
            cfg["query_user"],
            cfg["service_owner"],
            cfg["query_baseline_keys"],
        )


def restore(cfg):
    # Binary restore intentionally bypasses dpkg so recovery does not depend on
    # package-manager state. Report the temporary bookkeeping mismatch to the
    # operator; the next upgrade's forced reinstall reconciles it.
    stop(cfg["service"])
    shutil.copy2(pathlib.Path(cfg["backup_dir"]) / "semaphore.bin", cfg["binary"])
    shutil.copy2(pathlib.Path(cfg["backup_dir"]) / "semaphore-final.db", cfg["db"])
    os.chown(cfg["db"], int(cfg["db_uid"]), int(cfg["db_gid"]))
    os.chmod(cfg["db"], int(cfg["db_mode"], 8))
    start_and_verify(
        cfg,
        cfg["current_version"],
        cfg["current_binary_sha256"],
        cfg["baseline"],
    )


def notify(webhook_file, title, message):
    path = pathlib.Path(webhook_file)
    try:
        webhook = path.read_text(encoding="utf-8").strip()
        body = json.dumps(
            {"link_names": 1, "attachments": [{"title": title, "text": message, "fallback": title,
              "color": "good" if title.startswith("✅") else "warning" if title.startswith("⚠️") else "danger"}]}
        ).encode()
        request = urllib.request.Request(
            webhook, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                raise RuntimeError(f"Slack returned HTTP {response.status}")
    finally:
        path.unlink(missing_ok=True)


def write_result(path, result):
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(target)


def write_result_best_effort(configured_path, result):
    """Try every result path without preventing the notification attempt."""
    errors = []
    for path in dict.fromkeys((configured_path, DEFAULT_RESULT_FILE)):
        try:
            write_result(path, result)
            return path, errors
        except Exception as error:
            errors.append(f"{path}: {error}"[:500])
    return None, errors


def main():
    for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, interrupted)
    cfg = {
        "mode": "unknown",
        "webhook_file": DEFAULT_WEBHOOK_FILE,
        "notification_suppress_marker": DEFAULT_SUPPRESS_MARKER,
        "result_file": DEFAULT_RESULT_FILE,
        "skip_notifications": False,
    }
    result = {"status": "failed", "mode": "unknown", "error": "unexpected exit"}
    exit_code = 1
    rollback_recovery = None
    boundary_crossed = False
    result["service_stop_attempted"] = False
    try:
        if len(sys.argv) != 2:
            raise RuntimeError("usage: semaphore-upgrade-detached <config.json>")
        loaded = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise RuntimeError("transaction configuration is not an object")
        cfg.update(loaded)
        result["mode"] = cfg["mode"]
        # Observed transaction state, not the exception type, drives safety
        # reporting. Rollback does not mutate the binary before its boundary.
        result["binary_unchanged"] = cfg["mode"] == "rollback"
        result["reading_path_check"] = (
            "skipped" if cfg.get("skip_reading_path_check", False) else "pending"
        )
        # The unit can be active while waiting here. Ansible can finish and
        # Semaphore can persist the launching row before any service stop.
        wait_for_jobs(cfg)
        boundary_crossed = True
        if cfg["mode"] == "upgrade":
            result["service_stop_attempted"] = True
            stop(cfg["service"])
            final_db = pathlib.Path(cfg["backup_dir"]) / "semaphore-final.db"
            sqlite_backup(cfg["db"], final_db)
            start_and_verify(
                cfg,
                cfg["target_version"],
                cfg["target_binary_sha256"],
                cfg["baseline"],
            )
            result = {
                "status": "success",
                "mode": "upgrade",
                "version": cfg["target_version"],
                "reading_path_check": "skipped" if cfg.get("skip_reading_path_check", False) else "passed",
            }
        elif cfg["mode"] == "rollback":
            current = pathlib.Path(cfg["pre_rollback_dir"])
            rollback_recovery = {
                "version": version(cfg["binary"]),
                "sha256": sha256(cfg["binary"]),
                "counts": counts(cfg["db"]),
            }
            # The saved upgrade target need not be the version currently
            # running when an older rollback generation is selected.
            cfg["report_from_version"] = rollback_recovery["version"]
            cfg["report_from_edition"] = (
                cfg["target_edition"] if rollback_recovery["sha256"] == cfg["target_binary_sha256"]
                else cfg["current_edition"] if rollback_recovery["sha256"] == cfg["current_binary_sha256"]
                else "不明（保存済みhashと不一致）"
            )
            sqlite_backup(cfg["db"], current / "semaphore.db")
            shutil.copy2(cfg["binary"], current / "semaphore.bin")
            result["binary_unchanged"] = False
            result["service_stop_attempted"] = True
            restore(cfg)
            result = {
                "status": "success",
                "mode": "rollback",
                "version": cfg["current_version"],
                "dpkg_bookkeeping": DPKG_BOOKKEEPING_NOTE,
                "reading_path_check": "skipped" if cfg.get("skip_reading_path_check", False) else "passed",
            }
        else:
            raise RuntimeError("invalid transaction mode")
        exit_code = 0
    except Exception as error:
        result["error"] = str(error)[:500]
        if not boundary_crossed:
            try:
                if cfg.get("mode") == "upgrade":
                    undo_install_without_stop(cfg)
                    result["binary_restored"] = True
                    result["dpkg_bookkeeping"] = DPKG_BOOKKEEPING_NOTE
                if isinstance(error, BoundaryTimeout):
                    result["status"] = "aborted"
                    exit_code = 0
            except Exception as recovery_error:
                result["recovery_error"] = str(recovery_error)[:500]
        elif cfg.get("mode") == "upgrade":
            try:
                restore(cfg)
                result["rollback"] = "success"
                result["dpkg_bookkeeping"] = DPKG_BOOKKEEPING_NOTE
            except Exception as rollback_error:
                result["rollback"] = "failed"
                result["rollback_error"] = str(rollback_error)[:500]
        elif cfg.get("mode") == "rollback" and rollback_recovery:
            try:
                stop(cfg["service"])
                current = pathlib.Path(cfg["pre_rollback_dir"])
                shutil.copy2(current / "semaphore.bin", cfg["binary"])
                shutil.copy2(current / "semaphore.db", cfg["db"])
                os.chown(cfg["db"], int(cfg["db_uid"]), int(cfg["db_gid"]))
                os.chmod(cfg["db"], int(cfg["db_mode"], 8))
                start_and_verify(
                    cfg,
                    rollback_recovery["version"],
                    rollback_recovery["sha256"],
                    rollback_recovery["counts"],
                )
                result["pre_rollback_recovery"] = "success"
            except Exception as recovery_error:
                result["pre_rollback_recovery"] = "failed"
                result["recovery_error"] = str(recovery_error)[:500]
    finally:
        title, message = notification_text(cfg, result)
        marker = pathlib.Path(cfg.get("notification_suppress_marker", DEFAULT_SUPPRESS_MARKER))
        suppressed = bool(cfg.get("skip_notifications", False)) or marker.exists()
        result["notification"] = {
            "suppressed": suppressed,
            "title": title,
            "message": message,
        }
        try:
            print(json.dumps({"notification": result["notification"]}, sort_keys=True), flush=True)
        except Exception:
            pass
        result_file, result_write_errors = write_result_best_effort(
            cfg.get("result_file", DEFAULT_RESULT_FILE), result
        )
        if suppressed:
            try:
                pathlib.Path(cfg.get("webhook_file", DEFAULT_WEBHOOK_FILE)).unlink(missing_ok=True)
            except Exception:
                pass
        else:
            try:
                notify(cfg.get("webhook_file", DEFAULT_WEBHOOK_FILE), title, message)
                result["notification"]["sent"] = True
            except Exception as notify_error:
                result["notification"]["sent"] = False
                result["notification"]["error"] = str(notify_error)[:500]
        if result_write_errors:
            result["result_write_errors"] = result_write_errors
        write_result_best_effort(result_file or DEFAULT_RESULT_FILE, result)
        try:
            marker.unlink(missing_ok=True)
        except Exception:
            pass
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
