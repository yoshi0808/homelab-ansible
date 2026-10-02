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


HEADER_RE = re.compile(r"^(\S+)\s+\(([^)]+)\)")
CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}")


def entries_newer_than_installed(package, installed, output):
    """Return changelog entries after installed, or None when the boundary is unknown."""
    lines = output.splitlines()
    headers = [(index, match) for index, line in enumerate(lines)
               if (match := HEADER_RE.match(line))]
    if not headers:
        return None

    compare_version = installed
    if headers[0][1].group(1) != package:
        try:
            source_version = subprocess.run(
                ["dpkg-query", "-W", "--showformat=${source:Version}", package],
                capture_output=True,
                check=False,
                text=True,
                timeout=10,
            ).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            source_version = ""
        if source_version:
            compare_version = source_version

    try:
        import apt_pkg
        apt_pkg.init()
    except ImportError:
        return None

    selected = []
    found_boundary = False
    for index, header in headers:
        if apt_pkg.version_compare(header.group(2), compare_version) <= 0:
            found_boundary = True
            break
        next_index = next((next_header for next_header, _ in headers
                           if next_header > index), len(lines))
        selected.extend(lines[index:next_index])
    return "\n".join(selected) if found_boundary and selected else None


def latest_entry(output):
    """Return only the newest changelog entry, or an empty string."""
    lines = output.splitlines()
    started = False
    entry = []
    for line in lines:
        if HEADER_RE.match(line):
            if started:
                break
            started = True
        if started:
            entry.append(line)
    return "\n".join(entry)


def changelog_note(package, installed, is_new, timeout_seconds, cve_limit):
    """Return a concise note and CVEs limited to this update's changelog entries."""
    try:
        output = subprocess.run(
            ["apt", "changelog", package],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return "changelog取得不可", [], 0
    if not output.strip():
        return "changelog取得不可", [], 0

    scope_unknown = False
    if is_new:
        relevant = latest_entry(output)
    else:
        relevant = entries_newer_than_installed(package, installed, output)
        if relevant is None:
            relevant = latest_entry(output)
            scope_unknown = True

    bullets = [line.strip()[2:].strip() for line in relevant.splitlines()
               if line.startswith("  * ")]
    if not bullets:
        return "changelog取得不可", [], 0
    cves = sorted(set(CVE_RE.findall(relevant)))
    summary = bullets[0]
    if scope_unknown:
        summary += " (CVE範囲未確定: 最新項目のみ)"
    return summary, cves[:cve_limit], max(0, len(cves) - cve_limit)


def main():
    limit = 10
    timeout = 60
    cve_limit = 5
    args = iter(sys.argv[1:])
    for arg in args:
        if arg == "--limit":
            limit = max(0, int(next(args)))
        elif arg == "--timeout":
            timeout = max(0, int(next(args)))
        elif arg == "--cve-limit":
            cve_limit = max(0, int(next(args)))
        else:
            raise SystemExit("usage: proxmox-patch-changelog-collect.py [--limit N] [--timeout SECONDS]")
    records = parse_updates(sys.stdin.read())
    deadline = time.monotonic() + timeout
    for record in records[:limit]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            record["summary"], record["cves"], record["cve_overflow"] = (
                "changelog取得不可", [], 0)
            continue
        record["summary"], record["cves"], record["cve_overflow"] = changelog_note(
            record["package"], record["installed"], record["is_new"],
            min(20, max(1, remaining)), cve_limit)
    json.dump(records[:limit], sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
