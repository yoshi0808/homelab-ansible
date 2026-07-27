#!/usr/bin/env bash
set -euo pipefail

echo "[pre-commit] checking staged changes..."

staged_files="$(git -c core.quotepath=false diff --cached --name-only --diff-filter=ACMR || true)"

if [[ -z "$staged_files" ]]; then
  echo "[pre-commit] no staged files"
  exit 0
fi

# core.quotepath=false stops git from octal-escaping+quoting non-ASCII paths
# (which made them invisible to every grep/case match below: dangerous_files,
# vault-header, and the YAML syntax check all silently skipped such files).
# A path can still come back quoted if it contains a literal newline, quote,
# or backslash; for this check group, a name we cannot read is not "safe",
# it is "unjudged" — fail closed instead of silently skipping it.
quoted_paths="$(echo "$staged_files" | grep -E '^"' || true)"
if [[ -n "$quoted_paths" ]]; then
  echo "ERROR: staged path(s) cannot be safely checked (still quoted after core.quotepath=false):"
  echo "$quoted_paths"
  echo "These names likely contain a newline, quote, or backslash. Rename before committing."
  exit 1
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

yaml_files=()
while IFS= read -r f; do
  [[ -n "$f" ]] || continue
  yaml_files+=("$f")
done < <(echo "$staged_files" | grep -Ei '\.ya?ml$' || true)

if [[ ${#yaml_files[@]} -gt 0 ]]; then
  if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found; cannot run staged YAML syntax check"
    exit 1
  fi
  if ! python3 "$(dirname "${BASH_SOURCE[0]}")/check-staged-yaml.py" "${yaml_files[@]}"; then
    echo "ERROR: staged YAML syntax check failed (see above)"
    exit 1
  fi
fi

"$(dirname "${BASH_SOURCE[0]}")/check-tester-gate.sh"

echo "[pre-commit] OK"
