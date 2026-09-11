#!/usr/bin/env python3
"""Read-only observations. Health decisions belong to the controller."""
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


def collect():
    status = run(["zpool", "status", "-P", "-p"])
    disks = decoded(["lsblk", "--json", "--paths", "--output", "NAME,TYPE,PKNAME"])
    # Resolve only actual leaf paths printed in the pool config, never all disks.
    paths = sorted(set(re.findall(r"^\s+(/dev/\S+)\s+\S+\s+\d+\s+\d+\s+\d+\s*$",
                                 status["stdout"], re.M)))
    parents = {}

    def walk(rows):
        for row in rows:
            parents[row["name"]] = row.get("pkname") or row["name"]
            walk(row.get("children", []))

    if isinstance(disks.get("json"), dict):
        walk(disks["json"].get("blockdevices", []))
    devices = []
    for path in paths:
        resolved = os.path.realpath(path)
        namespace = parents.get(resolved)
        item = {"vdev": path, "resolved": resolved, "namespace": namespace}
        if namespace and re.fullmatch(r"/dev/nvme\d+n\d+", namespace):
            item["identity"] = decoded(["nvme", "id-ctrl", namespace, "-o", "json"])
            item["health"] = decoded(["nvme", "smart-log", namespace, "-o", "json"])
        else:
            item["error"] = "UnsupportedOrUnmappedVdev"
        devices.append(item)
    return {"schema_version": 1, "collected_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(),
            "zpool": status, "lsblk": disks, "devices": devices}


if __name__ == "__main__":
    print(json.dumps(collect()))
