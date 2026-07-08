#!/usr/bin/env bash
# PreToolUse hook (Bash): catch ssh / git commit / git push even when
# wrapped in a shell indirection like `bash -c "..."` or `sh -c "..."`.
#
# settings.json's deny rules (Bash(ssh*), Bash(git commit*), Bash(git
# push*)) only match the literal prefix of the submitted command string, so
# `bash -c "ssh host cmd"` bypasses them: the string starts with "bash", not
# "ssh". This hook inspects the full command string for these tokens
# anywhere in it, closing that specific wrapper-based gap.
#
# This is defense-in-depth, not a complete guarantee: a command built via
# variable concatenation, encoding, or other obfuscation can still evade a
# string-based check like this one. See docs/ai/prompts/core.md for the
# broader trust model (the human commit/push/ssh gate is the real backstop).
set -euo pipefail

input="$(cat)"
command="$(jq -r '.tool_input.command // empty' <<<"$input")"

[[ -z "$command" ]] && exit 0

# Boundary class: whitespace, common shell separators, path slash, and both
# quote characters -- so `bash -c "ssh ..."` / `sh -c '...'` are still
# caught (the token is immediately preceded/followed by a quote, not
# whitespace, once unwrapped from the outer command string).
b='[[:space:];&|/'"'"'"]'
ssh_re="(^|$b)ssh($b|\$)"
commit_re="(^|$b)git[[:space:]]+commit($b|\$)"
push_re="(^|$b)git[[:space:]]+push($b|\$)"

block() {
  echo "Blocked: command contains '$1' (even inside a wrapper such as bash -c/sh -c), which is denied. $2" >&2
  exit 2
}

[[ "$command" =~ $ssh_re ]] && block "ssh" "SSH access is not permitted for Claude Code in this repo."
[[ "$command" =~ $commit_re ]] && block "git commit" "Commits must be made by the user, not Claude Code."
[[ "$command" =~ $push_re ]] && block "git push" "Pushes must be made by the user, not Claude Code."

exit 0
