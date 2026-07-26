#!/bin/bash
# ubuntu-full-upgrade-simulate.sh
# Collects apt-get update/check/full-upgrade(simulation) results and outputs JSON.
# Shell responsibility: collection and JSON formatting only. No judgments
# (important-component matching, remove/replacement classification, Status
# determination are all done in Ansible tasks — docs/ai/context/operations/healthcheck.md / requirement §11).

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
# The full Inst/Remv lines are also passed through so the Python step below
# can extract the versions already present in them — no additional apt
# command is run for the version detail (2026-07-12_014 requirement §実施1).
inst_names=$(printf '%s\n' "$sim_out" | grep -oP '^Inst \K\S+' | sort -u)
remv_names=$(printf '%s\n' "$sim_out" | grep -oP '^Remv \K\S+' | sort -u)
inst_lines=$(printf '%s\n' "$sim_out" | grep '^Inst ' | sort -u)
remv_lines=$(printf '%s\n' "$sim_out" | grep '^Remv ' | sort -u)

# Ubuntu phased updates (staged rollouts): apt defers some upgrades and
# reports them (under LC_ALL=C, set above) as
#   The following upgrades have been deferred due to phasing:
#     <pkg> <pkg> ...            (2-space-indented, wrapped, names only —
#                                 the simulation prints no versions here)
# These get no Inst line, yet `apt list --upgradable` counts them, which is
# exactly the count mismatch seen on monnie (test_result 018 T-4). Collected
# so report/notification can reconcile candidates + phased against
# `apt list --upgradable` (2026-07-12_019 §実施1). Collection only — they are
# deliberately excluded from all judgement (see tasks/classify.yml header).
phased_names=$(printf '%s\n' "$sim_out" | awk '
  /^The following upgrades have been deferred due to phasing:/ { in_section = 1; next }
  in_section && /^ / { for (i = 1; i <= NF; i++) print $i; next }
  in_section { in_section = 0 }
' | sort -u)

# Versions for the phased-back packages: the deferred section above prints
# names only, so this is the one permitted read-only auxiliary lookup
# (2026-07-12_019 改訂制約: apt-cache policy reads the local package cache
# only — no network fetch, no package-state change; re-running apt-get
# update etc. stays forbidden). One batch invocation for all names.
phased_policy=""
if [ -n "$phased_names" ]; then
  # Intentionally unquoted: expand the newline-separated name list into
  # one argument per package.
  # shellcheck disable=SC2086
  phased_policy=$(apt-cache policy $phased_names 2>&1)
fi

# Packages explicitly kept back by the operator with `apt-mark hold`.
# `apt-mark showhold` only reads dpkg selections; like phased_detail above,
# this is notification/reconciliation data and is not an input to Status or
# apply judgement. Keep the command result separately so a collection error
# is not misreported as a package name.
hold_out=$(apt-mark showhold 2>&1)
hold_rc=$?
hold_names=""
if [ "$hold_rc" -eq 0 ]; then
  hold_names=$(printf '%s\n' "$hold_out" | sed '/^[[:space:]]*$/d' | sort -u)
fi

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
INST_LINES="$inst_lines" \
REMV_LINES="$remv_lines" \
PHASED_NAMES="$phased_names" \
PHASED_POLICY="$phased_policy" \
HOLD_RC="$hold_rc" \
HOLD_TAIL="$(printf '%s\n' "$hold_out" | tail -20)" \
HOLD_NAMES="$hold_names" \
REBOOT_REQUIRED_FLAG="$reboot_required_flag" \
python3 - << 'PYEOF'
import json
import os
import re
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

# Version extraction from the raw apt -s plan lines (still collection +
# formatting only, no judgement — docs/ai/context/operations/healthcheck.md):
#   Inst <pkg> [<oldver>] (<newver> <source> [...])
#     [<oldver>] is absent for a fresh install -> "old" stays ""
#   Remv <pkg> [<ver>]
INST_RE = re.compile(r"^Inst (\S+)(?: \[([^\]]*)\])?(?: \(([^\s)]+))?")
REMV_RE = re.compile(r"^Remv (\S+)(?: \[([^\]]*)\])?")


def lines(env_name):
    return [x for x in os.environ.get(env_name, "").splitlines() if x]


def inst_detail():
    out = []
    for line in lines("INST_LINES"):
        m = INST_RE.match(line)
        if m:
            out.append({"name": m.group(1),
                        "old": m.group(2) or "",
                        "new": m.group(3) or ""})
    return out


def remv_detail():
    out = []
    for line in lines("REMV_LINES"):
        m = REMV_RE.match(line)
        if m:
            out.append({"name": m.group(1),
                        "version": m.group(2) or ""})
    return out


def _clean_policy_version(value):
    # Defensive: strip a possible "(phased N%)" annotation (observed only in
    # the version table on ansy's apt, but cheap to guard on the value
    # lines too) and map apt's "(none)" placeholder to "".
    value = re.sub(r"\s*\(phased \d+%\)$", "", value.strip())
    return "" if value == "(none)" else value


def phased_detail():
    # Versions come from the PHASED_POLICY apt-cache output (LC_ALL=C):
    #   <pkg>:                       <- column 0, trailing colon
    #     Installed: <ver>|(none)
    #     Candidate: <ver>|(none)
    #     Version table: ...         <- indented, ignored
    # A name apt-cache could not resolve simply has no section -> both
    # versions stay "" (rendered as "?" by the Ansible-side template).
    # Keys are installed/candidate (not old/new) so the notification
    # template can tell phased entries apart from inst_detail entries.
    policy = {}
    current = None
    for line in os.environ.get("PHASED_POLICY", "").splitlines():
        if line and not line[0].isspace() and line.rstrip().endswith(":"):
            current = line.rstrip()[:-1]
            policy[current] = {"installed": "", "candidate": ""}
        elif current is not None:
            stripped = line.strip()
            if stripped.startswith("Installed:"):
                policy[current]["installed"] = _clean_policy_version(stripped[len("Installed:"):])
            elif stripped.startswith("Candidate:"):
                policy[current]["candidate"] = _clean_policy_version(stripped[len("Candidate:"):])
    return [{"name": n,
             "installed": policy.get(n, {}).get("installed", ""),
             "candidate": policy.get(n, {}).get("candidate", "")}
            for n in lines("PHASED_NAMES")]


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
    "apt_mark_showhold": {
        "rc": int(os.environ["HOLD_RC"]),
        "tail": os.environ.get("HOLD_TAIL", ""),
    },
    "simulation": {
        "rc": int(os.environ["SIM_RC"]),
        "inst": lines("INST_NAMES"),
        "remv": lines("REMV_NAMES"),
        "inst_detail": inst_detail(),
        "remv_detail": remv_detail(),
        "phased_detail": phased_detail(),
        "hold": lines("HOLD_NAMES"),
        "raw_tail": os.environ.get("SIM_RAW_TAIL", ""),
    },
    "reboot_required_flag": os.environ.get("REBOOT_REQUIRED_FLAG", "false") == "true",
}))
PYEOF
