#!/usr/bin/env bash
set -euo pipefail

has_check=0
for arg in "$@"; do
  if [[ "$arg" == "--check" ]]; then
    has_check=1
    break
  fi
done

if [[ "$has_check" -ne 1 ]]; then
  cat >&2 <<'EOF'
ERROR: scripts/safe-ansible-check.sh only runs ansible-playbook with --check.

Use:
  scripts/safe-ansible-check.sh playbooks/example.yml --check
EOF
  exit 2
fi

exec ansible-playbook "$@"
