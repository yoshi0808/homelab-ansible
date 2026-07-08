#!/usr/bin/env bash
# PreToolUse/PermissionRequest hook (Bash): block bare ansible-playbook.
#
# tester_mode/tester_gate is deprecated; ansible_check_mode (--check) is the
# safety gate now (docs/ai/prompts/core.md §18). Codex rules can allow broad
# Bash usage, so this hook blocks unguarded ansible-playbook invocations before
# they run.
set -euo pipefail

input="$(cat)"

command="$(
  jq -r '
    .tool_input.command //
    .tool_input.cmd //
    .tool_input.args.command //
    .toolInput.command //
    .input.command //
    .command //
    empty
  ' <<<"$input"
)"

[[ -z "$command" ]] && exit 0

# Match ansible-playbook as a command token, including shell-wrapped forms such
# as: /bin/bash -lc 'ansible-playbook ...'. Also catches absolute paths like
# /usr/bin/ansible-playbook, while avoiding words such as xansible-playbook.
[[ "$command" =~ (^|[^[:alnum:]_.-])([^[:space:]\;\\&\|\'\"\`\(\)]+/)?ansible-playbook($|[^[:alnum:]_.-]) ]] || exit 0

[[ "$command" =~ (^|[^[:alnum:]_.-])--(check|syntax-check)($|[^[:alnum:]_.-]) ]] && exit 0

cat >&2 <<'EOF'
Blocked: ansible-playbook must be run with --check or --syntax-check.

tester_mode is deprecated; ansible_check_mode is the safety gate now.
See docs/ai/prompts/core.md §18. Bare execution requires explicit human approval.
EOF
exit 2
