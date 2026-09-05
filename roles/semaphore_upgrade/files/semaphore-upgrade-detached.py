#!/usr/bin/env python3
"""Finish a Semaphore self-upgrade outside semaphore.service's cgroup."""

import hashlib
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
    "binary restored outside dpkg; dpkg -V may report a checksum mismatch until "
    "the next Semaphore upgrade reinstalls the pinned package"
)


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
            {"attachments": [{"title": title, "text": message, "color": "good" if "SUCCESS" in title else "danger"}]}
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
    try:
        if len(sys.argv) != 2:
            raise RuntimeError("usage: semaphore-upgrade-detached <config.json>")
        loaded = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise RuntimeError("transaction configuration is not an object")
        cfg.update(loaded)
        result["mode"] = cfg["mode"]
        result["reading_path_check"] = (
            "skipped" if cfg.get("skip_reading_path_check", False) else "pending"
        )
        if cfg["mode"] == "upgrade":
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
            sqlite_backup(cfg["db"], current / "semaphore.db")
            shutil.copy2(cfg["binary"], current / "semaphore.bin")
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
        if cfg.get("mode") == "upgrade":
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
        title = f"[Semaphore upgrade] {result['status'].upper()} ({cfg.get('mode', 'unknown')})"
        message = (
            f"host={os.uname().nodename} result={result}; "
            "the launching Semaphore job only confirmed detachment, not this result"
        )
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
