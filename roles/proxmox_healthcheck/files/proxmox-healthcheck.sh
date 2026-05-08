#!/bin/bash
# proxmox-healthcheck.sh
# Collects Proxmox health data and outputs JSON.
# Shell responsibility: collection and JSON formatting only. No judgments.

set -uo pipefail

pve_version=$(pveversion 2>/dev/null || echo "unavailable")

pvecm_raw=$(pvecm status 2>/dev/null || echo "unavailable")
quorate=$(echo "$pvecm_raw" | grep -i '^Quorate:' | awk '{print $2}')
quorate=${quorate:-unknown}

if zpool_raw=$(zpool status 2>/dev/null); then
  zpool_ok="true"
else
  zpool_ok="false"
  zpool_raw="unavailable"
fi

systemd_failed_raw=$(systemctl --failed --no-legend --no-pager 2>/dev/null || true)

svc_pve_cluster=$(systemctl is-active pve-cluster 2>/dev/null || echo "inactive")
svc_corosync=$(systemctl is-active corosync 2>/dev/null || echo "inactive")
svc_pvedaemon=$(systemctl is-active pvedaemon 2>/dev/null || echo "inactive")
svc_pveproxy=$(systemctl is-active pveproxy 2>/dev/null || echo "inactive")

root_used_pct=$(df -P / 2>/dev/null | awk 'NR==2 {gsub(/%/,""); print $5}')
root_used_pct=${root_used_pct:--1}

if apt_check_output=$(apt-get check 2>&1); then
  apt_check_ok="true"
else
  apt_check_ok="false"
fi

if [ -f /var/run/reboot-required ]; then
  reboot_required="true"
else
  reboot_required="false"
fi

qm_list_raw=$(qm list 2>/dev/null || echo "unavailable")
pct_list_raw=$(pct list 2>/dev/null || echo "unavailable")
pvesr_raw=$(pvesr status 2>/dev/null || echo "unavailable")
chrony_raw=$(chronyc tracking 2>/dev/null || echo "unavailable")

APT_CHECK_OK="$apt_check_ok" \
APT_CHECK_OUTPUT="${apt_check_output:-}" \
QUORATE="$quorate" \
PVECM_RAW="$pvecm_raw" \
ZPOOL_OK="$zpool_ok" \
ZPOOL_RAW="$zpool_raw" \
SYSTEMD_FAILED_RAW="${systemd_failed_raw:-}" \
SVC_PVE_CLUSTER="$svc_pve_cluster" \
SVC_COROSYNC="$svc_corosync" \
SVC_PVEDAEMON="$svc_pvedaemon" \
SVC_PVEPROXY="$svc_pveproxy" \
ROOT_USED_PCT="$root_used_pct" \
REBOOT_REQUIRED="$reboot_required" \
QM_LIST_RAW="$qm_list_raw" \
PCT_LIST_RAW="$pct_list_raw" \
PVESR_RAW="$pvesr_raw" \
CHRONY_RAW="$chrony_raw" \
PVE_VERSION="$pve_version" \
python3 - << 'PYEOF'
import json, os, datetime, re


def parse_zpool_states(raw):
    pools = []
    current_pool = None
    for line in raw.splitlines():
        m = re.match(r'^\s+pool:\s+(\S+)', line)
        if m:
            current_pool = m.group(1)
            continue
        m = re.match(r'^\s+state:\s+(\S+)', line)
        if m and current_pool is not None:
            pools.append({"name": current_pool, "state": m.group(1)})
            current_pool = None
    return pools


def parse_failed_units(raw):
    units = []
    if not raw or not raw.strip():
        return units
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r'^[●•\*]\s*', '', line)
        parts = line.split()
        if not parts:
            continue
        unit = parts[0]
        if '.' not in unit or unit.isdigit():
            continue
        units.append(unit)
    return units


def parse_pvesr_status(raw):
    entries = []
    if not raw or raw.strip() in ('unavailable', ''):
        return entries

    lines = raw.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if re.search(r'(?i)(job[\s_-]*id|jobid)', line):
            header_idx = i
            break

    start_idx = (header_idx + 1) if header_idx is not None else 0

    for line in lines[start_idx:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if not parts:
            continue
        job_id = parts[0]
        if job_id.startswith('-') or not re.match(r'\w+/', job_id):
            continue

        m = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
        if m:
            last_sync_str = m.group(1).strip()
            try:
                dt = datetime.datetime.strptime(last_sync_str, "%Y-%m-%d %H:%M:%S")
                last_sync_epoch = int(dt.timestamp())
            except ValueError:
                last_sync_epoch = -1
        else:
            last_sync_str = "N/A"
            last_sync_epoch = -1

        entries.append({
            "job_id": job_id,
            "last_sync": last_sync_str,
            "last_sync_epoch": last_sync_epoch
        })

    return entries


zpool_pools = parse_zpool_states(os.environ["ZPOOL_RAW"])
failed_units = parse_failed_units(os.environ["SYSTEMD_FAILED_RAW"])
repl_entries = parse_pvesr_status(os.environ["PVESR_RAW"])

print(json.dumps({
    "collected_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "pve_version": os.environ["PVE_VERSION"],
    "cluster": {
        "quorate": os.environ["QUORATE"],
        "raw": os.environ["PVECM_RAW"]
    },
    "zfs": {
        "collection_ok": os.environ["ZPOOL_OK"] == "true",
        "pools": zpool_pools,
        "raw": os.environ["ZPOOL_RAW"]
    },
    "replication": {
        "entries": repl_entries,
        "raw": os.environ["PVESR_RAW"]
    },
    "systemd": {
        "failed_count": len(failed_units),
        "failed_units": failed_units
    },
    "services": {
        "pve_cluster": os.environ["SVC_PVE_CLUSTER"],
        "corosync": os.environ["SVC_COROSYNC"],
        "pvedaemon": os.environ["SVC_PVEDAEMON"],
        "pveproxy": os.environ["SVC_PVEPROXY"]
    },
    "filesystem": {
        "root_used_pct": int(os.environ["ROOT_USED_PCT"])
    },
    "apt": {
        "check_ok": os.environ["APT_CHECK_OK"] == "true",
        "check_output": os.environ["APT_CHECK_OUTPUT"]
    },
    "reboot_required": os.environ["REBOOT_REQUIRED"] == "true",
    "vms": {
        "list": os.environ["QM_LIST_RAW"]
    },
    "cts": {
        "list": os.environ["PCT_LIST_RAW"]
    },
    "chrony": {
        "tracking": os.environ["CHRONY_RAW"]
    }
}))
PYEOF
