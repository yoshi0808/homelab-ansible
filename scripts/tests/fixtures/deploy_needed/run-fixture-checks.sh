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
  # R1 (docs/ai/reviews/precommit_checks_extension/2026-08-05_001_requirement.md,
  # AC1-AC3): newly-added playbooks/*.yml with no roles/semaphore_templates
  # catalog entry -> advisory only, exit 0 in all three cases.
  [newplaybook_ac1_no_catalog_entry]=0
  [newplaybook_ac2_has_catalog_entry]=0
  [newplaybook_ac3_existing_modified]=0
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
  [newplaybook_ac1_no_catalog_entry]="新規playbookにSemaphoreボタンがありません"
)

# fixture name -> newline-separated substrings that MUST NOT appear in stdout
declare -A must_not_contain=(
  [ac5_unrelated_change]="配備が要る"
  [r9_run_host_override]="(authy, monnie)"
  # AC2: playbook already has a catalog entry -> no advisory at all.
  [newplaybook_ac2_has_catalog_entry]="Semaphoreボタンがありません"
  # AC3: only an existing playbook's *content* changed (git status M, not A)
  # -> no advisory, even though the catalog fixture deliberately has no
  # entry for it (proves this is Added-only, not the broader ACMR set).
  [newplaybook_ac3_existing_modified]="Semaphoreボタンがありません"
)

# Fixtures using the before/after two-commit layout (see "Editing a
# fixture" below) instead of the plain flat-tree layout the rest use.
before_after_fixtures=(
  newplaybook_ac3_existing_modified
)
_is_before_after() {
  local name="$1"
  local f
  for f in "${before_after_fixtures[@]}"; do
    [[ "$f" == "$name" ]] && return 0
  done
  return 1
}

overall_fail=0

for name in $(printf '%s\n' "${!expected_exit[@]}" | sort); do
  src="$fixtures_dir/$name"
  if [[ ! -d "$src" ]]; then
    echo "ERROR: fixture directory missing: $src"
    overall_fail=1
    continue
  fi

  work="$(mktemp -d)"
  if _is_before_after "$name"; then
    # Two-commit layout: before/ is committed first (so its files are HEAD
    # content), then after/ is laid on top and staged -- this is what makes
    # `git diff --cached --diff-filter=A` correctly report only genuinely
    # new files as Added, and a same-path content change as Modified. The
    # single-commit flat-tree layout below cannot represent that distinction
    # at all (with zero prior commits, every file is trivially "Added").
    (cd "$work" && git init -q)
    if [[ -d "$src/before" ]]; then
      cp -a "$src/before"/. "$work"/
      (cd "$work" && git add -A . && git commit -q -m fixture-base)
    fi
    cp -a "$src/after"/. "$work"/
    (cd "$work" && git add -A .)
  else
    cp -a "$src"/. "$work"/
    (cd "$work" && git init -q && git add -A .)
  fi

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

# ---------------------------------------------------------------------------
# AC4 (R2, docs/ai/reviews/precommit_checks_extension/2026-08-05_001_requirement.md):
# "staged 一覧の取得が1箇所になっており、引用符が残るパスに対してシェルと
# Pythonが同じ判断をする". Not representable as a static tracked fixture
# tree (a filename containing a literal backslash/quote is exactly what
# every commit to *this* repository must not carry, since it would trip
# this same pre-commit gate on its own commit) -- so it is built in a
# throwaway temp dir at run time instead, the same way the fixtures above
# are materialized, just without a tracked source tree to copy from.
# ---------------------------------------------------------------------------

precommit_sh="$fixtures_dir/../../../git-pre-commit-check.sh"

echo "=== ac4_quoted_path_parity (shell and python must both fail closed) ==="
work="$(mktemp -d)"
(cd "$work" && git init -q)
# Single-quoted so the backslash is a literal byte in the filename, not a
# shell escape -- confirmed empirically that git still quotes this even
# with -c core.quotepath=false (that setting only stops octal-escaping of
# non-ASCII bytes; a literal quote/backslash/newline in a name is always
# quoted).
: > "$work"/'weird\name.yml'
(cd "$work" && git add -A .)

set +e
sh_output="$(cd "$work" && bash "$precommit_sh" 2>&1)"
sh_actual=$?
py_output="$(python3 "$checker" --repo-root "$work" 2>&1)"
py_actual=$?
set -e
rm -rf "$work"

echo "$sh_output" | sed 's/^/  [shell]  /'
echo "$py_output"  | sed 's/^/  [python] /'

fixture_ok=1
if [[ "$sh_actual" -eq 0 ]]; then
  echo "  -> FAIL (shell exited 0 on a quoted staged path; should fail closed)"
  fixture_ok=0
fi
if [[ "$sh_output" != *"cannot be safely checked"* ]]; then
  echo "  -> FAIL (shell did not report the quoted-path guard)"
  fixture_ok=0
fi
if [[ "$py_actual" -eq 0 ]]; then
  echo "  -> FAIL (python exited 0 on a quoted staged path; should fail closed)"
  fixture_ok=0
fi
if [[ "$py_output" != *"quoted"* ]]; then
  echo "  -> FAIL (python did not report the quoted-path guard)"
  fixture_ok=0
fi
if [[ "$fixture_ok" -eq 1 ]]; then
  echo "  -> PASS (shell exit $sh_actual, python exit $py_actual, both fail closed)"
else
  overall_fail=1
fi
echo

# ---------------------------------------------------------------------------
# AC4 continued: proves the staged list is actually a single source of
# truth, not "python still asks git itself, and --staged-paths is ignored".
# A path that real git would never report as staged (it was never written
# to disk / never `git add`ed) is fed in via --staged-paths and must still
# drive R4's catalog match; the same repo checked without --staged-paths
# (self-derived) must NOT match it, since that path genuinely is not staged.
# ---------------------------------------------------------------------------

echo "=== ac4_given_staged_paths_is_authoritative ==="
work="$(mktemp -d)"
mkdir -p "$work/playbooks" "$work/roles/deployment_drift_check/defaults"
cat > "$work/playbooks/real_thing.yml" <<'EOF'
---
- name: Fixture placeholder
  hosts: quory
  gather_facts: false
  tasks: []
EOF
cat > "$work/roles/deployment_drift_check/defaults/main.yml" <<'EOF'
---
deployment_drift_check_files:
  - hosts: [quory]
    src: roles/fake/files/never-written-to-disk.py
    dest: /usr/local/sbin/never-written-to-disk.py
    playbook: playbooks/real_thing.yml
EOF
(cd "$work" && git init -q && git add -A .)

set +e
# Self-derived: the fake src was never created, so real `git diff --cached`
# cannot possibly report it staged -> R4 must NOT fire.
self_derived_output="$(python3 "$checker" --repo-root "$work" 2>&1)"
self_derived_actual=$?
# Given: feed the fake src in via --staged-paths even though it is not
# really on disk or in the index -> R4 must fire, proving this script used
# the given list as-is rather than re-deriving from git.
given_output="$(printf '%s\n' "roles/fake/files/never-written-to-disk.py" | python3 "$checker" --repo-root "$work" --staged-paths - 2>&1)"
given_actual=$?
set -e
rm -rf "$work"

echo "$self_derived_output" | sed 's/^/  [self-derived] /'
echo "$given_output"        | sed 's/^/  [given]        /'

fixture_ok=1
if [[ "$self_derived_actual" -ne 0 ]]; then
  echo "  -> FAIL (self-derived run should exit 0; R5 has nothing to complain about here)"
  fixture_ok=0
fi
if [[ "$self_derived_output" == *"配備が要る"* ]]; then
  echo "  -> FAIL (self-derived run matched R4 on a path that was never actually staged)"
  fixture_ok=0
fi
if [[ "$given_actual" -ne 0 ]]; then
  echo "  -> FAIL (given-list run should exit 0; R5 has nothing to complain about here)"
  fixture_ok=0
fi
if [[ "$given_output" != *"配備が要る: \`playbooks/real_thing.yml\`(quory)"* ]]; then
  echo "  -> FAIL (given-list run did not match R4 on the path passed via --staged-paths)"
  fixture_ok=0
fi
if [[ "$fixture_ok" -eq 1 ]]; then
  echo "  -> PASS (--staged-paths is authoritative: self-derived misses it, given finds it)"
else
  overall_fail=1
fi
echo

exit "$overall_fail"
