#!/bin/bash
# proxmox-patch-predryrun-collect.sh
# Pre-patch re-dry-run data collection. Returns JSON.
# Shell responsibility: collection and JSON formatting only. No judgments.

set -uo pipefail

collected_at=$(date +"%Y-%m-%dT%H:%M:%S%z")
node_name=$(hostname -s)

# apt-get update (refresh package lists only)
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

COLLECTED_AT="$collected_at" \
NODE_NAME="$node_name" \
APT_UPDATE_OK="$apt_update_ok" \
APT_UPDATE_OUTPUT="${apt_update_output:-}" \
APT_CHECK_OK="$apt_check_ok" \
APT_CHECK_OUTPUT="${apt_check_output:-}" \
SIM_OK="$sim_ok" \
SIM_OUTPUT="$sim_output" \
REBOOT_REQUIRED="$reboot_required" \
python3 - << 'PYEOF'
import json, os

print(json.dumps({
    "collected_at": os.environ["COLLECTED_AT"],
    "node": os.environ["NODE_NAME"],
    "apt_update_ok": os.environ["APT_UPDATE_OK"] == "true",
    "apt_update_output": os.environ["APT_UPDATE_OUTPUT"],
    "apt_check_ok": os.environ["APT_CHECK_OK"] == "true",
    "apt_check_output": os.environ["APT_CHECK_OUTPUT"],
    "sim_ok": os.environ["SIM_OK"] == "true",
    "sim_output": os.environ["SIM_OUTPUT"],
    "reboot_required": os.environ["REBOOT_REQUIRED"] == "true",
}))
PYEOF
