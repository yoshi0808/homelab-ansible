#!/usr/bin/env bash
# Runs scripts/check-doc-consistency.py against every fixture below and
# checks the exit code against the table recorded here.
#
# check-doc-consistency.py reads content from the git index (`git show
# :<path>`), the same convention scripts/check-staged-yaml.py uses (see
# docs/ai/reviews/norm_drift_mechanical_check/2026-08-01_003_implement.md
# §2.2 for why). That means it needs a real git index to read from - but a
# fixture *stored* as its own git repository would mean a nested `.git`
# directory committed inside this repository, which is what triggered the
# 2026-08-01 revision request this script exists to satisfy.
#
# So the fixtures under this directory are plain file trees with no `.git`
# of their own. This script materializes each one into a throwaway git repo
# in a temp directory at run time (`git init` + `git add -A`, no commit -
# `git show :<path>` and `git ls-files` both read the index directly, no
# commit required), runs the checker against that temp copy, and deletes it
# afterward. Nothing under scripts/tests/fixtures/ itself is ever a git
# repository.
set -euo pipefail

fixtures_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
checker="$fixtures_dir/../../check-doc-consistency.py"

# fixture name -> expected exit code of check-doc-consistency.py
declare -A expected_exit=(
  [clean_baseline]=0
  [check1_tester_gate_mismatch]=1
  [check2_model_effort_mismatch]=1
  [check3_broken_link]=1
  [empty_playbooks]=2
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
  if [[ "$actual" -eq "$want" ]]; then
    echo "  -> PASS (exit $actual)"
  else
    echo "  -> FAIL (exit $actual, expected $want)"
    overall_fail=1
  fi
  echo
done

exit "$overall_fail"
