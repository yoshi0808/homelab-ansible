#!/usr/bin/env bash
# Runs the local capture fixture once for each AC1 case, in a separate process
# and with a separate temporary spool.  It prints each PLAY RECAP so callers
# can compare pre-change and post-change task counts without touching reports/.
set -u

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../../.." && pwd)"
fixture="${script_dir}/test_capture_check_mode.yml"
stage="$(mktemp -d)"
trap 'rm -rf "${stage}"' EXIT

mkdir -p "${stage}/playbooks"
ln -s "${repo_root}/roles" "${stage}/roles"
cp "${fixture}" "${stage}/playbooks/fixture.yml"

overall_rc=0

run_case() {
  local label="$1"
  local inherited_check_mode="$2"
  local expected_records="$3"
  local expect_written_id="$4"
  local extra_args="$5"
  local create_marker="$6"
  local spool_parent_is_file="$7"
  local case_dir marker spool output rc

  case_dir="$(mktemp -d)"
  marker="${case_dir}/marker"
  spool="${case_dir}/spool"
  if [[ "${spool_parent_is_file}" == "true" ]]; then
    : > "${case_dir}/spool-parent"
    spool="${case_dir}/spool-parent/spool"
  else
    mkdir -p "${spool}"
  fi
  output="$(CAPTURE_FIXTURE_MARKER="${marker}" \
    CAPTURE_FIXTURE_SPOOL="${spool}" \
    script -qec "ansible-playbook --extra-vars '{\"fixture_include_from_check_mode_false_block\":${inherited_check_mode},\"fixture_expected_records\":${expected_records},\"fixture_expect_written_id\":${expect_written_id},\"fixture_create_marker\":${create_marker}}' ${extra_args} ${stage}/playbooks/fixture.yml" /dev/null 2>&1)"
  rc=$?

  if [[ ${rc} -eq 0 ]] && grep -q 'PLAY RECAP' <<<"${output}"; then
    echo "PASS  ${label}"
    grep -A1 'PLAY RECAP' <<<"${output}" | tail -n 1
  else
    echo "FAIL  ${label} (rc=${rc})"
    echo "${output}"
    overall_rc=1
  fi

  rm -rf "${case_dir}"
}

run_case normal false 1 true "" true false
run_case inherited_check_mode_false true 1 true "" true false
run_case check_normal false 0 false "--check" true false
run_case check_inherited_check_mode_false true 0 false "--check" true false
run_case marker_absent false 0 false "" false false
run_case spool_parent_is_file false 0 false "" true true

exit "${overall_rc}"
