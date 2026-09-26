#!/usr/bin/env bash
# AC10: same fixture input fed to both roles' BLOCKED/MAINTENANCE_REQUIRED/
# MAJOR_UPGRADE_DETECTED/PATCH_READY formulas must produce the same result
# per scenario. Runs both roles' fixture playbooks (localhost only, no real
# hosts touched -- execution_boundary_policy.md EXEC-010), then diffs their
# per-scenario status output.
#
# Usage: roles/proxmox_patch_apply_node/tests/compare_dryrun_and_apply.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
DRYRUN_PLAYBOOK="$REPO_ROOT/roles/proxmox_patch_dryrun/tests/test_blocked_removes.yml"
APPLY_PLAYBOOK="$REPO_ROOT/roles/proxmox_patch_apply_node/tests/test_blocked_removes.yml"
DRYRUN_RESULT="/tmp/proxmox_patch_dryrun_test_results.json"
APPLY_RESULT="/tmp/proxmox_patch_apply_node_test_results.json"

run_playbook() {
  # ansible-playbook errors with "Ansible requires blocking IO" under some
  # harnesses (non-blocking stdio); `script` allocates a pty to work around
  # it without changing anything the playbook itself does.
  if command -v script >/dev/null 2>&1; then
    script -qec "ansible-playbook $1" /dev/null
  else
    ansible-playbook "$1"
  fi
}

echo "Running dryrun-side fixture playbook..."
run_playbook "$DRYRUN_PLAYBOOK" > /tmp/proxmox_patch_dryrun_test.log 2>&1 || {
  echo "FAILED: dryrun-side fixture playbook did not pass; see /tmp/proxmox_patch_dryrun_test.log"
  tail -n 40 /tmp/proxmox_patch_dryrun_test.log
  exit 1
}

echo "Running apply-side fixture playbook..."
run_playbook "$APPLY_PLAYBOOK" > /tmp/proxmox_patch_apply_node_test.log 2>&1 || {
  echo "FAILED: apply-side fixture playbook did not pass; see /tmp/proxmox_patch_apply_node_test.log"
  tail -n 40 /tmp/proxmox_patch_apply_node_test.log
  exit 1
}

python3 - "$DRYRUN_RESULT" "$APPLY_RESULT" <<'PYEOF'
import json
import sys

dryrun_path, apply_path = sys.argv[1], sys.argv[2]
dryrun = {item["id"]: item["status"] for item in json.load(open(dryrun_path))}
apply_ = {item["id"]: item["status"] for item in json.load(open(apply_path))}

if dryrun.keys() != apply_.keys():
    print("FAILED: scenario sets differ between dryrun and apply results")
    print("dryrun only:", sorted(set(dryrun) - set(apply_)))
    print("apply only:", sorted(set(apply_) - set(dryrun)))
    sys.exit(1)

mismatches = [
    (scenario_id, dryrun[scenario_id], apply_[scenario_id])
    for scenario_id in dryrun
    if dryrun[scenario_id] != apply_[scenario_id]
]

if mismatches:
    print("FAILED: dryrun and apply disagree on the following scenarios:")
    for scenario_id, dryrun_status, apply_status in mismatches:
        print(f"  - {scenario_id}: dryrun={dryrun_status} apply={apply_status}")
    sys.exit(1)

print(f"OK: dryrun and apply agree on all {len(dryrun)} scenarios:")
for scenario_id in sorted(dryrun):
    print(f"  - {scenario_id}: {dryrun[scenario_id]}")
PYEOF
