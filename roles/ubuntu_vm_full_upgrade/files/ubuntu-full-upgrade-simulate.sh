#!/bin/bash
# ubuntu-full-upgrade-simulate.sh
# Collects apt-get update/check/full-upgrade(simulation) results and outputs JSON.
# Shell responsibility: collection and JSON formatting only. No judgments
# (important-component matching, remove/replacement classification, Status
# determination are all done in Ansible tasks — core.md §7 / requirement §11).

set -uo pipefail
export LC_ALL=C DEBIAN_FRONTEND=noninteractive

update_out=$(apt-get update 2>&1)
update_rc=$?

check_out=$(apt-get check 2>&1)
check_rc=$?

sim_out=$(apt-get -s full-upgrade 2>&1)
sim_rc=$?

# Raw extraction only (no filtering/classification): apt -s output lines are
#   Inst <pkg> [<oldver>] (<newver> <source> [...])
#   Remv <pkg> [<ver>]
inst_names=$(printf '%s\n' "$sim_out" | grep -oP '^Inst \K\S+' | sort -u)
remv_names=$(printf '%s\n' "$sim_out" | grep -oP '^Remv \K\S+' | sort -u)

reboot_required_flag="false"
[ -f /var/run/reboot-required ] && reboot_required_flag="true"

UPDATE_RC="$update_rc" \
UPDATE_TAIL="$(printf '%s\n' "$update_out" | tail -20)" \
CHECK_RC="$check_rc" \
CHECK_TAIL="$(printf '%s\n' "$check_out" | tail -20)" \
SIM_RC="$sim_rc" \
SIM_RAW_TAIL="$(printf '%s\n' "$sim_out" | tail -400)" \
INST_NAMES="$inst_names" \
REMV_NAMES="$remv_names" \
REBOOT_REQUIRED_FLAG="$reboot_required_flag" \
python3 - << 'PYEOF'
import json
import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))


def lines(env_name):
    return [x for x in os.environ.get(env_name, "").splitlines() if x]


print(json.dumps({
    "collected_at": datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S%z"),
    "apt_update": {
        "rc": int(os.environ["UPDATE_RC"]),
        "tail": os.environ.get("UPDATE_TAIL", ""),
    },
    "apt_check": {
        "rc": int(os.environ["CHECK_RC"]),
        "tail": os.environ.get("CHECK_TAIL", ""),
    },
    "simulation": {
        "rc": int(os.environ["SIM_RC"]),
        "inst": lines("INST_NAMES"),
        "remv": lines("REMV_NAMES"),
        "raw_tail": os.environ.get("SIM_RAW_TAIL", ""),
    },
    "reboot_required_flag": os.environ.get("REBOOT_REQUIRED_FLAG", "false") == "true",
}))
PYEOF
