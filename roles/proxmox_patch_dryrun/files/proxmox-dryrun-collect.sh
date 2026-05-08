#!/bin/bash
# proxmox-dryrun-collect.sh
# Collects apt dry-run data and changelog diffs, outputs JSON.
# Shell responsibility: collection and JSON formatting only. No judgments.

set -uo pipefail

collected_at=$(date +"%Y-%m-%dT%H:%M:%SZ")
node_name=$(hostname -s)

# apt-get -s dist-upgrade simulation (no changes)
sim_output=$(LC_ALL=C apt-get -s dist-upgrade 2>&1) && sim_ok="true" || sim_ok="false"

# reboot-required check
if [ -f /var/run/reboot-required ]; then
  reboot_required="true"
else
  reboot_required="false"
fi

SIM_OK="$sim_ok" \
SIM_OUTPUT="$sim_output" \
REBOOT_REQUIRED="$reboot_required" \
NODE_NAME="$node_name" \
COLLECTED_AT="$collected_at" \
python3 - << 'PYEOF'
import json, os, re, subprocess

sim_ok = os.environ["SIM_OK"] == "true"
sim_output = os.environ["SIM_OUTPUT"]
reboot_required = os.environ["REBOOT_REQUIRED"] == "true"
node_name = os.environ["NODE_NAME"]
collected_at = os.environ["COLLECTED_AT"]

updates = []
removes = []

for line in sim_output.splitlines():
    # Inst pkg [old-ver] (new-ver source [...])
    m = re.match(r'^Inst (\S+)(?:\s+\[([^\]]+)\])?\s+\((\S+)\s+(.*?)\)', line)
    if m:
        name, old_ver, new_ver, source_info = m.group(1), m.group(2), m.group(3), m.group(4)
        security_repo = bool(re.search(
            r'security\.debian\.org|-security\b|Debian-Security', source_info, re.IGNORECASE
        ))
        updates.append({
            "name": name,
            "installed_version": old_ver,
            "candidate_version": new_ver,
            "is_new": old_ver is None,
            "security_repo": security_repo,
            "changelog_diff": ""
        })
        continue

    # Remv pkg [ver]
    m = re.match(r'^Remv (\S+)(?:\s+\[([^\]]+)\])?', line)
    if m:
        removes.append({"name": m.group(1), "installed_version": m.group(2)})


def get_changelog_diff(pkg_name, installed_version, is_new):
    try:
        result = subprocess.run(
            ["apt", "changelog", pkg_name],
            capture_output=True, text=True, timeout=60
        )
        full = result.stdout
    except Exception:
        return ""

    if not full.strip():
        return ""

    lines = full.splitlines()

    if is_new:
        # First (latest) entry only
        entry, started = [], False
        for line in lines:
            if re.match(r'^\S+\s+\(', line):
                if started:
                    break
                started = True
            if started:
                entry.append(line)
        return "\n".join(entry)

    # Entries newer than installed_version
    try:
        import apt_pkg
        apt_pkg.init()
        result_lines = []
        for line in lines:
            m = re.match(r'^\S+\s+\(([^)]+)\)', line)
            if m:
                if apt_pkg.version_compare(m.group(1), installed_version) <= 0:
                    break
            result_lines.append(line)
        return "\n".join(result_lines)
    except Exception:
        return full[:3000]


for u in updates:
    u["changelog_diff"] = get_changelog_diff(u["name"], u["installed_version"], u["is_new"])

print(json.dumps({
    "collected_at": collected_at,
    "node": node_name,
    "sim_ok": sim_ok,
    "reboot_required": reboot_required,
    "updates": updates,
    "removes": removes
}))
PYEOF
