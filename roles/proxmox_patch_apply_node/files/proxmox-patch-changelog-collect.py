#!/usr/bin/env python3
"""Collect concise package changelog evidence from apt simulation output."""

import json
import re
import subprocess
import sys
import time


def parse_updates(simulation):
    """Return package/version records from apt-get -s `Inst` lines."""
    records = []
    for line in simulation.splitlines():
        fields = line.split()
        if len(fields) < 3 or fields[0] != "Inst":
            continue
        package = fields[1]
        is_new = fields[2].startswith("(")
        installed = "" if is_new else fields[2].strip("[]")
        candidate_field = fields[2] if is_new else (fields[3] if len(fields) > 3 else "")
        candidate = candidate_field.lstrip("(").rstrip(")")
        records.append({
            "package": package,
            "installed": installed,
            "candidate": candidate,
            "is_new": is_new,
        })
    return records


def changelog_note(package, timeout_seconds):
    """Return the newest bullet and CVE identifiers, without classifying it."""
    try:
        output = subprocess.run(
            ["apt", "changelog", package],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return "changelog取得不可", []
    if not output.strip():
        return "changelog取得不可", []
    bullets = [line.strip()[2:].strip() for line in output.splitlines()
               if line.startswith("  * ")]
    if not bullets:
        return "changelog取得不可", []
    return bullets[0], sorted(set(re.findall(r"CVE-\d{4}-\d{4,7}", output)))


def main():
    limit = 10
    timeout = 60
    args = iter(sys.argv[1:])
    for arg in args:
        if arg == "--limit":
            limit = max(0, int(next(args)))
        elif arg == "--timeout":
            timeout = max(0, int(next(args)))
        else:
            raise SystemExit("usage: proxmox-patch-changelog-collect.py [--limit N] [--timeout SECONDS]")
    records = parse_updates(sys.stdin.read())
    deadline = time.monotonic() + timeout
    for record in records[:limit]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            record["summary"], record["cves"] = "changelog取得不可", []
            continue
        record["summary"], record["cves"] = changelog_note(
            record["package"], min(20, max(1, remaining)))
    json.dump(records[:limit], sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
