#!/bin/bash
# proxmox-snapshot-collect.sh
# Collects the snapshot inventory for guests hosted on THIS node and outputs JSON.
#
# Shell responsibility (core.md §7): collection and JSON formatting only.
# No staleness judgment here. The 7-day threshold is evaluated in Ansible tasks.
#
# Collection failures are reported as observed data (collection_ok / errors), not
# judged here. Ansible tasks decide how to treat them. This prevents a collection
# failure from being silently reported as "no snapshots / OK".
#
# The Proxmox "current" pseudo-entry is not a real snapshot (it marks the live
# state) and is structurally excluded. It is not a staleness decision.

set -uo pipefail

node=$(hostname)

NODE="$node" \
python3 - << 'PYEOF'
import json
import os
import subprocess
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
node = os.environ["NODE"]


def pvesh_json(path):
    """Run `pvesh get <path> --output-format json`.

    Returns (data, error). On success error is None. On failure data is None and
    error is a short string describing the failure.
    """
    try:
        proc = subprocess.run(
            ["pvesh", "get", path, "--output-format", "json"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as exc:
        return None, "exec failed: %s" % exc

    if proc.returncode != 0:
        return None, (proc.stderr or "").strip() or ("pvesh rc=%d" % proc.returncode)
    if not proc.stdout.strip():
        return None, "empty output"
    try:
        return json.loads(proc.stdout), None
    except ValueError as exc:
        return None, "json parse error: %s" % exc


errors = []
snapshots = []
collection_ok = True

resources, err = pvesh_json("/cluster/resources")
if err is not None:
    collection_ok = False
    errors.append({"scope": "cluster/resources", "error": err})
    resources = []

for res in resources:
    if res.get("type") not in ("qemu", "lxc"):
        continue
    if res.get("node") != node:
        continue

    gtype = res.get("type")
    vmid = res.get("vmid")
    guest_name = res.get("name", "")

    snaps, err = pvesh_json("/nodes/%s/%s/%s/snapshot" % (node, gtype, vmid))
    if err is not None:
        errors.append({
            "scope": "%s/%s/%s" % (node, gtype, vmid),
            "node": node, "type": gtype, "vmid": vmid, "error": err,
        })
        continue

    for snap in snaps:
        snapname = snap.get("name", "")
        if snapname == "current":
            continue
        snapshots.append({
            "vmid": vmid,
            "guest_name": guest_name,
            "type": gtype,
            "snapname": snapname,
            "snaptime": snap.get("snaptime", -1),
            "description": (snap.get("description") or "").strip(),
        })

print(json.dumps({
    "collected_at": datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S%z"),
    "node": node,
    "collection_ok": collection_ok,
    "errors": errors,
    "snapshots": snapshots,
}))
PYEOF
