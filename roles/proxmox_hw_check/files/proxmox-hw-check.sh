#!/bin/bash
# proxmox-hw-check.sh
# Collects Proxmox hardware info and outputs JSON.
# Shell responsibility: collection and JSON formatting only. No judgments.

set -uo pipefail

# CPU
cpu_model=$(lscpu 2>/dev/null | awk -F':[[:space:]]+' '/^Model name:/{print $2; exit}')
cpu_model=${cpu_model:-unknown}
cpu_sockets=$(lscpu 2>/dev/null | awk '/^Socket\(s\):/{print $NF; exit}')
cpu_sockets=${cpu_sockets:-0}
cpu_cores_per_socket=$(lscpu 2>/dev/null | awk '/^Core\(s\) per socket:/{print $NF; exit}')
cpu_cores_per_socket=${cpu_cores_per_socket:-0}
cpu_threads_per_core=$(lscpu 2>/dev/null | awk '/^Thread\(s\) per core:/{print $NF; exit}')
cpu_threads_per_core=${cpu_threads_per_core:-0}
cpu_total=$(lscpu 2>/dev/null | awk '/^CPU\(s\):/{print $NF; exit}')
cpu_total=${cpu_total:-0}

# Memory
mem_total_kb=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}')
mem_total_kb=${mem_total_kb:-0}

# ZFS pool summary
zpool_list_raw=$(zpool list -H -o name,size,alloc,free,cap,health 2>/dev/null || echo "unavailable")

# ZFS status (for scrub info)
zpool_status_raw=$(zpool status 2>/dev/null || echo "unavailable")

# Disk filesystems
df_raw=$(df -Ph 2>/dev/null || echo "unavailable")

# NIC stats (excluding loopback and transient virtual interfaces)
ip_link_raw=$(ip -s link show 2>/dev/null || echo "unavailable")

CPU_MODEL="$cpu_model" \
CPU_SOCKETS="$cpu_sockets" \
CPU_CORES_PER_SOCKET="$cpu_cores_per_socket" \
CPU_THREADS_PER_CORE="$cpu_threads_per_core" \
CPU_TOTAL="$cpu_total" \
MEM_TOTAL_KB="$mem_total_kb" \
ZPOOL_LIST_RAW="$zpool_list_raw" \
ZPOOL_STATUS_RAW="$zpool_status_raw" \
DF_RAW="$df_raw" \
IP_LINK_RAW="$ip_link_raw" \
python3 - << 'PYEOF'
import json, os, datetime, re


def safe_int(val, default=0):
    try:
        return int(str(val).strip())
    except (ValueError, AttributeError):
        return default


def parse_zpool_list(raw):
    if not raw or raw.strip() == 'unavailable':
        return []
    pools = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 6:
            continue
        name, size, alloc, free, cap, health = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
        pools.append({
            "name": name,
            "size": size,
            "alloc": alloc,
            "free": free,
            "capacity_pct": safe_int(cap.rstrip('%'), -1),
            "health": health
        })
    return pools


def parse_zpool_scrub(raw):
    if not raw or raw.strip() == 'unavailable':
        return []
    scrubs = []
    current_pool = None
    for line in raw.splitlines():
        m = re.match(r'^\s+pool:\s+(\S+)', line)
        if m:
            current_pool = m.group(1)
            continue
        m = re.match(r'^\s+scan:\s+(.*)', line)
        if m and current_pool is not None:
            scrubs.append({
                "pool": current_pool,
                "scan": m.group(1).strip()
            })
    return scrubs


def parse_df(raw):
    if not raw or raw.strip() == 'unavailable':
        return []
    filesystems = []
    lines = raw.splitlines()
    i = 1  # skip header
    while i < len(lines):
        parts = lines[i].split()
        if len(parts) == 1:
            # Long filesystem name on its own line (POSIX -P wrapping)
            filesystem = parts[0]
            i += 1
            if i < len(lines):
                p2 = lines[i].split()
                if len(p2) >= 5:
                    filesystems.append({
                        "filesystem": filesystem,
                        "size": p2[0], "used": p2[1], "avail": p2[2],
                        "use_pct": safe_int(p2[3].rstrip('%'), -1),
                        "mount": p2[4]
                    })
        elif len(parts) >= 6:
            filesystems.append({
                "filesystem": parts[0],
                "size": parts[1], "used": parts[2], "avail": parts[3],
                "use_pct": safe_int(parts[4].rstrip('%'), -1),
                "mount": parts[5]
            })
        i += 1
    return filesystems


def parse_nics(raw):
    if not raw or raw.strip() == 'unavailable':
        return []

    excluded_prefixes = ('lo', 'veth', 'tap', 'fwbr', 'fwln', 'fwpr', 'dummy')
    nics = []
    current_nic = None
    rx_header_seen = False
    tx_header_seen = False

    for line in raw.splitlines():
        m = re.match(r'^\d+:\s+(\S+?)[@:]\s', line)
        if m:
            if current_nic:
                nics.append(current_nic)
            name = m.group(1)
            if any(name.startswith(p) for p in excluded_prefixes):
                current_nic = None
                rx_header_seen = tx_header_seen = False
                continue
            state_m = re.search(r'\bstate\s+(\S+)', line)
            current_nic = {
                "name": name,
                "state": state_m.group(1) if state_m else 'UNKNOWN',
                "rx_packets": 0, "rx_errors": 0, "rx_dropped": 0,
                "tx_packets": 0, "tx_errors": 0, "tx_dropped": 0
            }
            rx_header_seen = tx_header_seen = False
            continue

        if current_nic is None:
            continue

        stripped = line.strip()
        if re.match(r'^RX:', stripped):
            rx_header_seen = True
            tx_header_seen = False
            continue
        if re.match(r'^TX:', stripped):
            tx_header_seen = True
            rx_header_seen = False
            continue
        if rx_header_seen:
            vals = stripped.split()
            if len(vals) >= 4:
                current_nic['rx_packets'] = safe_int(vals[1])
                current_nic['rx_errors'] = safe_int(vals[2])
                current_nic['rx_dropped'] = safe_int(vals[3])
            rx_header_seen = False
            continue
        if tx_header_seen:
            vals = stripped.split()
            if len(vals) >= 4:
                current_nic['tx_packets'] = safe_int(vals[1])
                current_nic['tx_errors'] = safe_int(vals[2])
                current_nic['tx_dropped'] = safe_int(vals[3])
            tx_header_seen = False
            continue

    if current_nic:
        nics.append(current_nic)

    for nic in nics:
        nic['total_packets'] = nic['rx_packets'] + nic['tx_packets']
        nic['total_errors'] = nic['rx_errors'] + nic['tx_errors']
        nic['total_dropped'] = nic['rx_dropped'] + nic['tx_dropped']

    return nics


_zpool_list_raw = os.environ['ZPOOL_LIST_RAW']
_zpool_status_raw = os.environ['ZPOOL_STATUS_RAW']
_df_raw = os.environ['DF_RAW']
_ip_link_raw = os.environ['IP_LINK_RAW']

zpool_pools = parse_zpool_list(_zpool_list_raw)
zpool_scrubs = parse_zpool_scrub(_zpool_status_raw)
filesystems = parse_df(_df_raw)
nics = parse_nics(_ip_link_raw)

collection_status = {
    "nics": _ip_link_raw.strip() != 'unavailable',
    "zfs_pools": _zpool_list_raw.strip() != 'unavailable',
    "zfs_scrub": _zpool_status_raw.strip() != 'unavailable',
    "disk": _df_raw.strip() != 'unavailable',
}

print(json.dumps({
    "collected_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "collection_status": collection_status,
    "cpu": {
        "model": os.environ['CPU_MODEL'].strip(),
        "sockets": safe_int(os.environ['CPU_SOCKETS']),
        "cores_per_socket": safe_int(os.environ['CPU_CORES_PER_SOCKET']),
        "threads_per_core": safe_int(os.environ['CPU_THREADS_PER_CORE']),
        "total_cpus": safe_int(os.environ['CPU_TOTAL'])
    },
    "memory": {
        "total_mb": safe_int(os.environ['MEM_TOTAL_KB']) // 1024
    },
    "zfs": {
        "pools": zpool_pools,
        "scrub": zpool_scrubs
    },
    "disk": {
        "filesystems": filesystems
    },
    "nics": nics
}))
PYEOF
