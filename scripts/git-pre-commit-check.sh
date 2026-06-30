#!/usr/bin/env bash
set -euo pipefail

echo "[pre-commit] checking staged changes..."

staged_files="$(git diff --cached --name-only --diff-filter=ACMR || true)"

if [[ -z "$staged_files" ]]; then
  echo "[pre-commit] no staged files"
  exit 0
fi

if command -v gitleaks >/dev/null 2>&1; then
  gitleaks protect --staged --verbose
else
  echo "ERROR: gitleaks not found"
  exit 1
fi

dangerous_files="$(echo "$staged_files" | grep -Ei '(\.key|\.pem|\.p12|\.pfx|\.ovpn|id_rsa|id_ed25519)$' || true)"
if [[ -n "$dangerous_files" ]]; then
  echo "ERROR: dangerous secret-like file staged:"
  echo "$dangerous_files"
  exit 1
fi

ipv4_hits="$(
  git diff --cached -U0 -- \
    '*.yml' '*.yaml' '*.md' '*.sh' '*.j2' '*.cfg' '*.ini' '*.txt' \
  | grep -E '^\+[^+].*([0-9]{1,3}\.){3}[0-9]{1,3}' \
  | grep -Ev '127\.0\.0\.1|0\.0\.0\.0|255\.255\.255\.255' || true
)"
if [[ -n "$ipv4_hits" ]]; then
  echo "ERROR: IPv4 literal found in staged additions:"
  echo "$ipv4_hits"
  echo "Use DNS names or runtime name resolution instead."
  exit 1
fi

while IFS= read -r file; do
  [[ -f "$file" ]] || continue

  case "$file" in
    *vault*.yml|*vault*.yaml|*secret*.yml|*secret*.yaml|*.vault.yml|*.vault.yaml|*.secret.yml|*.secret.yaml)
      first_line="$(head -n 1 "$file" || true)"
      if [[ "$first_line" != "\$ANSIBLE_VAULT;"* ]]; then
        echo "ERROR: vault/secret-like YAML is not Ansible Vault encrypted:"
        echo "$file"
        echo "First line must start with: \$ANSIBLE_VAULT;"
        exit 1
      fi
      ;;
  esac
done <<< "$staged_files"

echo "[pre-commit] OK"
