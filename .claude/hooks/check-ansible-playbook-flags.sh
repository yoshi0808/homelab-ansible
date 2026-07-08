#!/usr/bin/env bash
# PreToolUse hook (Bash): block bare `ansible-playbook` execution.
#
# tester_mode/tester_gate is deprecated; ansible_check_mode (--check) is the
# safety gate now (docs/ai/prompts/core.md §18). settings.json allows Bash(*)
# broadly, so this hook is what keeps a real, unguarded ansible-playbook
# invocation from running without --check or --syntax-check.
set -euo pipefail

input="$(cat)"
command="$(jq -r '.tool_input.command // empty' <<<"$input")"

[[ -z "$command" ]] && exit 0

# Match `ansible-playbook` as an actual command token (start-of-string,
# whitespace, `/`, or a shell separator on each side), not merely as a
# substring of some other filename -- e.g. this hook script's own path.
[[ "$command" =~ (^|[[:space:];\&\|/])ansible-playbook([[:space:];\&\|]|$) ]] || exit 0

[[ "$command" == *--check* || "$command" == *--syntax-check* ]] && exit 0

echo "Blocked: ansible-playbook must be run with --check or --syntax-check (tester_mode is deprecated). See docs/ai/prompts/core.md §18. Bare execution requires explicit human approval." >&2
exit 2
