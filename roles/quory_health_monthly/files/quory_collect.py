#!/usr/bin/env python3
"""Read-only observations of quory itself. Health decisions belong to the controller."""
import json
import os
import re
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo


def run(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30,
                                env={**os.environ, "LC_ALL": "C", "TZ": "Asia/Tokyo"},
                                check=False)
        return {"rc": result.returncode, "stdout": result.stdout}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"rc": -1, "error": type(exc).__name__, "stdout": ""}


def decoded(argv):
    result = run(argv)
    if result["rc"] == 0:
        try:
            result["json"] = json.loads(result["stdout"])
        except ValueError:
            result["error"] = "InvalidJSON"
    return result


def meminfo():
    values = {}
    with open("/proc/meminfo", encoding="utf-8") as stream:
        for line in stream:
            match = re.fullmatch(r"(\w+):\s+(\d+)\s*kB\s*\n?", line)
            if match:
                values[match[1]] = int(match[2]) * 1024
    return values


def mounted_target(mountpoint):
    """The mount actually covering mountpoint, which may differ if it isn't a separate mount.

    `df <path>` silently reports whatever filesystem contains <path> even when
    <path> itself is not a mount point (e.g. /boot/efi never mounted separately
    would report the root filesystem). Only findmnt confirms the real target.
    """
    result = run(["findmnt", "--noheadings", "--output", "TARGET", "--target", mountpoint])
    if result["rc"] != 0:
        return None
    lines = [line.strip() for line in result["stdout"].splitlines() if line.strip()]
    return lines[0] if lines else None


def df_entry(mountpoint):
    target = mounted_target(mountpoint)
    if target != mountpoint:
        return {"mountpoint": mountpoint, "error": "not_mounted", "actual_mount": target}
    # -P (POSIX output format) and --output are mutually exclusive in GNU df;
    # --output already pins one line per filesystem for a single mountpoint arg.
    result = run(["df", "--output=source,fstype,size,used,avail,pcent", "-B1", mountpoint])
    if result["rc"] != 0:
        return {"mountpoint": mountpoint, "error": "df_failed", "rc": result["rc"]}
    lines = [line for line in result["stdout"].splitlines() if line.strip()]
    if len(lines) < 2:
        return {"mountpoint": mountpoint, "error": "df_no_output"}
    fields = lines[1].split()
    if len(fields) != 6:
        return {"mountpoint": mountpoint, "error": "df_unparsed", "raw": lines[1]}
    source, fstype, size, used, avail, pcent = fields
    return {"mountpoint": mountpoint, "source": source, "fstype": fstype,
            "size_bytes": size, "used_bytes": used, "avail_bytes": avail,
            "use_percent_raw": pcent}


def nvme_namespaces(lsblk):
    """Raise if the enumeration cannot be trusted; never fall back to "zero devices".

    Only rc=0 with well-formed JSON (blockdevices present, every row carrying
    NAME/TYPE as strings) may be read as a genuine "checked, none present".
    Anything else — a failed command, missing/malformed structure — means "we
    don't know" and must raise. This check does not lean on any other
    function's behavior (e.g. decoded() only attempting to parse JSON when
    rc=0): rc is verified again here, at the point that decides whether the
    JSON payload may be trusted, so this function's contract holds even if a
    caller hands it a JSON payload alongside a non-zero rc.
    """
    if lsblk.get("rc") != 0:
        raise ValueError("lsblk command failed")
    namespaces = []

    def walk(rows):
        if not isinstance(rows, list):
            raise ValueError("lsblk rows not a list")
        for row in rows:
            # We asked lsblk for exactly --output NAME,TYPE, so every row must
            # carry both as strings; a row like {} (present but uninterpretable)
            # must not be treated the same as "checked, this row isn't NVMe".
            if not isinstance(row, dict) or not isinstance(row.get("name"), str) \
                    or not isinstance(row.get("type"), str):
                raise ValueError("lsblk row missing name/type")
            if row["type"] == "disk" and re.fullmatch(r"/dev/nvme\d+n\d+", row["name"]):
                namespaces.append(row["name"])
            walk(row.get("children", []))

    payload = lsblk.get("json")
    if not isinstance(payload, dict) or "blockdevices" not in payload:
        raise ValueError("lsblk output missing blockdevices")
    walk(payload["blockdevices"])
    return sorted(set(namespaces))


def collect():
    filesystems = {"root": df_entry("/"), "efi": df_entry("/boot/efi")}
    memory = meminfo()
    lsblk = decoded(["lsblk", "--json", "--paths", "--output", "NAME,TYPE"])
    try:
        namespaces = nvme_namespaces(lsblk)
        lsblk_valid = True
    except ValueError:
        namespaces, lsblk_valid = [], False
    devices = []
    for namespace in namespaces:
        devices.append({
            "namespace": namespace,
            "identity": decoded(["nvme", "id-ctrl", namespace, "-o", "json"]),
            "health": decoded(["nvme", "smart-log", namespace, "-o", "json"]),
        })
    return {"schema_version": 1, "collected_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(),
            "filesystems": filesystems, "memory": memory, "lsblk": lsblk, "lsblk_valid": lsblk_valid,
            "devices": devices, "nvme_transport_observed": bool(namespaces) if lsblk_valid else None}


if __name__ == "__main__":
    print(json.dumps(collect()))
