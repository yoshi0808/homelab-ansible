#!/bin/bash
# proxmox-dryrun-collect.sh
# Collects apt dry-run data and changelog diffs, outputs JSON.
# Shell responsibility: collection and JSON formatting only. No judgments.

set -uo pipefail

collected_at=$(date +"%Y-%m-%dT%H:%M:%SZ")
node_name=$(hostname -s)

# apt-get update (refresh package lists only, no package installation)
apt_update_output=$(apt-get update -qq 2>&1) && apt_update_ok="true" || apt_update_ok="false"

# apt-get check (dpkg/apt consistency check)
apt_check_output=$(apt-get check 2>&1) && apt_check_ok="true" || apt_check_ok="false"

# apt-get -s dist-upgrade simulation (no changes)
sim_output=$(LC_ALL=C apt-get -s dist-upgrade 2>&1) && sim_ok="true" || sim_ok="false"

# reboot-required check
if [ -f /var/run/reboot-required ]; then
  reboot_required="true"
else
  reboot_required="false"
fi

APT_UPDATE_OK="$apt_update_ok" \
APT_UPDATE_OUTPUT="${apt_update_output:-}" \
APT_CHECK_OK="$apt_check_ok" \
APT_CHECK_OUTPUT="${apt_check_output:-}" \
SIM_OK="$sim_ok" \
SIM_OUTPUT="$sim_output" \
REBOOT_REQUIRED="$reboot_required" \
NODE_NAME="$node_name" \
COLLECTED_AT="$collected_at" \
python3 - << 'PYEOF'
import json, os, re, subprocess

apt_update_ok = os.environ["APT_UPDATE_OK"] == "true"
apt_update_output = os.environ["APT_UPDATE_OUTPUT"]
apt_check_ok = os.environ["APT_CHECK_OK"] == "true"
apt_check_output = os.environ["APT_CHECK_OUTPUT"]
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

    # Entries newer than installed_version.
    # Source-derived packages (e.g. libtalloc2 from samba source) have changelog
    # entry versions in the source package's version space, not the binary version
    # space.  Comparing a samba source version like 2:4.17.x+dfsg against a
    # libtalloc2 binary version like 2:2.4.2-1 always yields "> 0", so the break
    # never fires and the entire decades-long changelog is returned.
    # Fix: when the first changelog entry names a different package, use the
    # installed binary's source version (dpkg source:Version) for comparison.
    cmp_version = installed_version
    for line in lines:
        m = re.match(r'^(\S+)\s+\(', line)
        if m:
            if m.group(1) != pkg_name:
                try:
                    r = subprocess.run(
                        ["dpkg-query", "-W", "--showformat=${source:Version}", pkg_name],
                        capture_output=True, text=True, timeout=10
                    )
                    sv = r.stdout.strip()
                    if sv:
                        cmp_version = sv
                except Exception:
                    pass
            break

    try:
        import apt_pkg
        apt_pkg.init()
        result_lines = []
        for line in lines:
            m = re.match(r'^\S+\s+\(([^)]+)\)', line)
            if m:
                if apt_pkg.version_compare(m.group(1), cmp_version) <= 0:
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
    "apt_update_ok": apt_update_ok,
    "apt_update_output": apt_update_output,
    "apt_check_ok": apt_check_ok,
    "apt_check_output": apt_check_output,
    "sim_ok": sim_ok,
    "reboot_required": reboot_required,
    "updates": updates,
    "removes": removes
}))
PYEOF
