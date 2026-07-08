#!/usr/bin/env bash
# PreToolUse hook (Bash): gate `ansible-playbook` execution.
#
# tester_mode/tester_gate is deprecated; ansible_check_mode (--check) is the
# safety gate now (docs/ai/prompts/core.md §18). settings.json allows Bash(*)
# broadly, so this hook is what keeps Claude Code from running real
# ansible-playbook invocations unsupervised:
#   - bare execution (no --check/--syntax-check): hard block. Real changes
#     require explicit human approval (core.md §16 APPLY).
#   - --syntax-check: always allowed. Pure YAML/syntax validation, no host
#     contact, not "testing" in any meaningful sense.
#   - --check (without --syntax-check): ask for confirmation each time. This
#     is real dry-run testing against real hosts -- core.md §16 assigns this
#     to Tester for independent verification, so Claude Code shouldn't be
#     able to silently self-test and skip dispatching to Tester.
set -euo pipefail

input="$(cat)"
command="$(jq -r '.tool_input.command // empty' <<<"$input")"

[[ -z "$command" ]] && exit 0

# Match `ansible-playbook` as an actual command token (start-of-string,
# whitespace, `/`, or a shell separator on each side), not merely as a
# substring of some other filename -- e.g. this hook script's own path.
[[ "$command" =~ (^|[[:space:];\&\|/])ansible-playbook([[:space:];\&\|]|$) ]] || exit 0

if [[ "$command" == *--syntax-check* ]]; then
  exit 0
fi

if [[ "$command" == *--check* ]]; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "ask",
      permissionDecisionReason: "ansible-playbook --check is real dry-run testing against real hosts. Per core.md §16, this should go through Tester for independent verification, not Claude Code self-testing. Confirm only if this is a deliberate one-off check, not a substitute for dispatching to Tester."
    }
  }'
  exit 0
fi

echo "Blocked: ansible-playbook must be run with --check or --syntax-check (tester_mode is deprecated). See docs/ai/prompts/core.md §18. Bare execution requires explicit human approval." >&2
exit 2
