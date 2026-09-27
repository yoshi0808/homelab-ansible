#!/usr/bin/env bash
# Runs test_failure_notification.yml (proxmox_patch_notifications_2b AC2 /
# AC1c(restore側) / AC3 / AC7) for every scenario, checks each one against an
# expected exit code and expected/forbidden substrings in the combined
# output, and prints one PASS/FAIL line per scenario.
#
# Why this exists (not just `ansible-playbook -e scenario=... fixture.yml`):
#   1. Several scenarios are DESIGNED to fail (the real role re-raises the
#      original error after notifying) — running them raw produces
#      `failed=2` in the PLAY RECAP with no indication of whether that
#      failure was the intended one or a fixture bug. This script decides
#      pass/fail from expected rc + expected message content instead.
#   2. The fixture's notify.yml / capture.yml includes use the same
#      single-dot "{{ playbook_dir }}/../roles/..." form as the real role
#      (roles/proxmox_restore_vm_placement/tasks/main.yml). That only resolves
#      when playbook_dir's parent directory has "roles" as a sibling, the
#      way playbooks/*.yml does in production. This script stages a COPY
#      of the fixture under <tmp>/playbooks/ with <tmp>/roles symlinked to
#      this repo's real roles/ tree, so the include paths resolve exactly
#      as they do in production (including notify.yml's own internal
#      include of capture.yml, which otherwise fails to be found).
#
# Exit code: 0 if every scenario matched its expectation, 1 otherwise.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FIXTURE="${SCRIPT_DIR}/test_failure_notification.yml"

STAGE="$(mktemp -d)"
REPORT_DIR="$(mktemp -d)"
trap 'rm -rf "${STAGE}" "${REPORT_DIR}"' EXIT

mkdir -p "${STAGE}/playbooks"
ln -s "${REPO_ROOT}/roles" "${STAGE}/roles"
cp "${FIXTURE}" "${STAGE}/playbooks/fixture.yml"

export FIXTURE_REPORT_DIR="${REPORT_DIR}"
export CLAUDECODE=1

overall_rc=0

# label|scenario(-e scenario=...)|expected_rc(0 or nonzero, "0"/"nz")|must-contain regex(es, ;-joined)|must-not-contain regex(es, ;-joined, may be empty)|extra ansible-playbook args (may be empty, e.g. "--check")
#
# "success_check_mode" (AC7) reuses the "success" scenario under --check: the
# fixture's migrate command has no native check-mode support, so Ansible
# auto-skips it under --check (shown as "skipping:" in the output) instead of
# running a real qm/pct migrate — the same behavior the real role relies on
# for its own destructive-phase tasks.
CASES=(
  "healthcheck_fail|healthcheck_fail|nz|対象node: pve1;失敗task: Abort if post-restore healthcheck is not OK;VMが退避先に残っている可能性があります。;proxmox_restore_vm_placement failed:||"
  "migrate_partial_fail|migrate_partial_fail|nz|戻せたVM: 101;失敗task: Migrate non-HA QEMU VMs back to target_node;proxmox_restore_vm_placement failed: One or more items failed|戻せたVM: 101, 102|"
  "success|success|0||included:.*notify.yml|"
  "success_check_mode|success|0|skipping:|included:.*notify.yml|--check"
  "notify_body_fail|notify_body_fail|nz|proxmox_restore_vm_placement failed: One or more items failed||"
  "notify_include_fail|notify_include_fail|nz|proxmox_restore_vm_placement failed: One or more items failed||"
  "report_save_fail|report_save_fail|nz|report: report保存失敗;proxmox_restore_vm_placement failed: One or more items failed||"
)

for case_line in "${CASES[@]}"; do
  IFS='|' read -r label scenario expect_rc must_contain must_not_contain extra_args <<<"${case_line}"

  out="$(script -qec "ansible-playbook -e scenario=${scenario} -e capture_collector_marker=/nonexistent-fixture-capture-marker ${extra_args} ${STAGE}/playbooks/fixture.yml" /dev/null 2>&1)"
  rc=$?

  ok=1
  reason=""

  if [[ "${expect_rc}" == "0" && "${rc}" -ne 0 ]]; then
    ok=0
    reason="expected rc=0, got rc=${rc}"
  elif [[ "${expect_rc}" == "nz" && "${rc}" -eq 0 ]]; then
    ok=0
    reason="expected non-zero rc, got rc=0"
  fi

  if [[ ${ok} -eq 1 && -n "${must_contain}" ]]; then
    IFS=';' read -ra patterns <<<"${must_contain}"
    for p in "${patterns[@]}"; do
      if ! grep -qE -- "${p}" <<<"${out}"; then
        ok=0
        reason="missing expected text: ${p}"
        break
      fi
    done
  fi

  if [[ ${ok} -eq 1 && -n "${must_not_contain}" ]]; then
    IFS=';' read -ra patterns <<<"${must_not_contain}"
    for p in "${patterns[@]}"; do
      if grep -qE -- "${p}" <<<"${out}"; then
        ok=0
        reason="found forbidden text: ${p}"
        break
      fi
    done
  fi

  if [[ ${ok} -eq 1 ]]; then
    echo "PASS  ${label} (rc=${rc})"
  else
    echo "FAIL  ${label}: ${reason}"
    echo "--- output (${label}) ---"
    echo "${out}"
    echo "--- end output ---"
    overall_rc=1
  fi
done

exit "${overall_rc}"
