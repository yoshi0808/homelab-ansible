#!/usr/bin/env bash
# AC8 (proxmox_patch_judgment_2a): runs test_hc_collection_failure.yml once
# per failure-mode scenario, each as a fresh `ansible-playbook` process (see
# that file's header for why a loop within one play cannot be used here --
# the initial judgment's `_post_hc_json is not defined` check needs a
# genuinely fresh variable namespace, not one reset via set_fact).
#
# Usage: roles/proxmox_patch_apply_node/tests/test_hc_collection_failure.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PLAYBOOK="$REPO_ROOT/roles/proxmox_patch_apply_node/tests/test_hc_collection_failure.yml"

run_playbook() {
  # ansible-playbook errors with "Ansible requires blocking IO" under some
  # harnesses (non-blocking stdio); `script` allocates a pty to work around
  # it without changing anything the playbook itself does.
  #
  # All scenario vars are passed as ONE --extra-vars JSON blob (not
  # `-e key=value`): ansible's k=v extra-vars parsing tokenizes on
  # whitespace, which mangles a JSON value containing spaces/commas.
  if command -v script >/dev/null 2>&1; then
    script -qec "ansible-playbook $PLAYBOOK -e '$1'" /dev/null
  else
    ansible-playbook "$PLAYBOOK" -e "$1"
  fi
}

declare -a SCENARIOS=(
  'command_failed|{"hc_scenario_id":"command_failed","hc_scenario_raw":{"failed":true,"rc":1,"stdout":""},"hc_expect_initial":"UNKNOWN","hc_expect_retry":"CRITICAL"}'
  'collection_failed_empty_output|{"hc_scenario_id":"collection_failed_empty_output","hc_scenario_raw":{"failed":false,"rc":0,"stdout":""},"hc_expect_initial":"UNKNOWN","hc_expect_retry":"CRITICAL"}'
  'json_parse_failed|{"hc_scenario_id":"json_parse_failed","hc_scenario_raw":{"failed":false,"rc":0,"stdout":"not-valid-json{"},"hc_expect_initial":"UNKNOWN","hc_expect_retry":"CRITICAL"}'
)

fail=0
for entry in "${SCENARIOS[@]}"; do
  id="${entry%%|*}"
  extra_vars_json="${entry#*|}"
  echo "Running scenario: $id"
  logfile="/tmp/proxmox_patch_apply_hc_collection_failure_${id}.log"
  if ! run_playbook "$extra_vars_json" > "$logfile" 2>&1; then
    echo "FAILED: scenario $id did not pass; see $logfile"
    tail -n 40 "$logfile"
    fail=1
  else
    echo "OK: $id"
  fi
done

if [ "$fail" -ne 0 ]; then
  exit 1
fi

echo "All AC8 collection/parse-failure scenarios PASS (initial=UNKNOWN, retry=CRITICAL)."
