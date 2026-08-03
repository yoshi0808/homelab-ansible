#!/usr/bin/env bash
# Runs scripts/check-deploy-needed.py against every fixture below and checks
# both the exit code and expected/forbidden output substrings.
#
# check-deploy-needed.py reads staged content from the git INDEX (`git show
# :<path>`, `git diff --cached`, `git ls-files`) -- same convention as
# scripts/check-doc-consistency.py and its scripts/tests/fixtures/. That
# means it needs a real git index to read from, and specifically needs
# `git diff --cached` to report every fixture file as staged. This script
# materializes each fixture into a throwaway git repo in a temp directory
# (`git init` + `git add -A`, no commit -- with zero prior commits,
# `git diff --cached` against the empty tree reports every added file as
# staged, which is exactly the "I just changed this" state each fixture
# wants to simulate), runs the checker against that temp copy, and deletes
# it afterward. Nothing under scripts/tests/fixtures/deploy_needed/ itself is
# ever a git repository.
set -euo pipefail

fixtures_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
checker="$fixtures_dir/../../../check-deploy-needed.py"

# fixture name -> expected exit code
declare -A expected_exit=(
  [ac4_catalog_file_changed]=0
  [ac5_unrelated_change]=0
  [ac6_missing_playbook]=1
  [ac8_template_changed]=0
  [r9_run_host_override]=0
)

# fixture name -> newline-separated substrings that MUST appear in stdout
declare -A must_contain=(
  [ac4_catalog_file_changed]="配備が要る: \`playbooks/incident_investigate_setup.yml\`(quory)"
  [ac6_missing_playbook]="playbooks/does_not_exist_setup.yml"
  [ac8_template_changed]="配備が要る可能性: \`playbooks/incident_investigate_setup.yml\`(role=incident_investigate)"
  # R9: hosts: [authy, monnie] but run_host: quory -- the message must show
  # the run_host override, not the raw hosts list, or the printed command
  # would match zero hosts in the real play (hosts: quory).
  [r9_run_host_override]="配備が要る: \`playbooks/recovery_push_setup.yml\`(quory)"
)

# fixture name -> newline-separated substrings that MUST NOT appear in stdout
declare -A must_not_contain=(
  [ac5_unrelated_change]="配備が要る"
  [r9_run_host_override]="(authy, monnie)"
)

overall_fail=0

for name in $(printf '%s\n' "${!expected_exit[@]}" | sort); do
  src="$fixtures_dir/$name"
  if [[ ! -d "$src" ]]; then
    echo "ERROR: fixture directory missing: $src"
    overall_fail=1
    continue
  fi

  work="$(mktemp -d)"
  cp -a "$src"/. "$work"/
  (cd "$work" && git init -q && git add -A .)

  set +e
  output="$(python3 "$checker" --repo-root "$work" 2>&1)"
  actual=$?
  set -e
  rm -rf "$work"

  want="${expected_exit[$name]}"
  echo "=== $name (expect exit $want) ==="
  echo "$output" | sed 's/^/  /'

  fixture_ok=1
  if [[ "$actual" -ne "$want" ]]; then
    echo "  -> FAIL (exit $actual, expected $want)"
    fixture_ok=0
  fi

  if [[ -n "${must_contain[$name]:-}" ]]; then
    if [[ "$output" != *"${must_contain[$name]}"* ]]; then
      echo "  -> FAIL (missing expected substring: ${must_contain[$name]})"
      fixture_ok=0
    fi
  fi

  if [[ -n "${must_not_contain[$name]:-}" ]]; then
    if [[ "$output" == *"${must_not_contain[$name]}"* ]]; then
      echo "  -> FAIL (forbidden substring present: ${must_not_contain[$name]})"
      fixture_ok=0
    fi
  fi

  if [[ "$fixture_ok" -eq 1 ]]; then
    echo "  -> PASS (exit $actual)"
  else
    overall_fail=1
  fi
  echo
done

exit "$overall_fail"
