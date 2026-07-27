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

# Checks the content staged in the git index (`git show :<path>`), not the
# working tree. What gets committed is the index, not the working tree, so
# checking the working tree lets plaintext-staged-then-encrypted-in-place
# slip through, and flags encrypted-staged-then-decrypted-in-place as a
# false positive. See check-staged-yaml.py's header comment for the same
# reasoning applied to the YAML syntax check.
while IFS= read -r file; do
  [[ -n "$file" ]] || continue

  case "$file" in
    *vault*.yml|*vault*.yaml|*secret*.yml|*secret*.yaml|*.vault.yml|*.vault.yaml|*.secret.yml|*.secret.yaml)
      # Symlinks (e.g. shared vault files linked from elsewhere) have index
      # content that is a target path string, not vault ciphertext; skip
      # them, matching check-staged-yaml.py's treatment of mode 120000.
      # ":(literal)" disables pathspec glob magic so a name containing
      # [seq]/*/? etc. is matched literally, not as a glob (otherwise a
      # symlink named e.g. "vault[s].yml" could match other staged paths
      # too, turning this into a multi-line result that never equals
      # "120000" and wrongly blocks a legitimate symlink commit).
      file_mode="$(git ls-files -s -- ":(literal)$file" | awk '{print $1}')"
      if [[ "$file_mode" == "120000" ]]; then
        continue
      fi

      # A name we cannot read the staged content for is not "safe", it is
      # "unjudged" — fail closed instead of silently skipping it (same
      # policy as the quoted-path guard above).
      if ! staged_content="$(git show ":$file" 2>/dev/null)"; then
        echo "ERROR: could not read staged content for vault/secret-like file (fail-closed):"
        echo "$file"
        exit 1
      fi

      first_line="$(head -n 1 <<< "$staged_content")"
      if [[ "$first_line" != "\$ANSIBLE_VAULT;"* ]]; then
        echo "ERROR: vault/secret-like YAML is not Ansible Vault encrypted (staged content checked):"
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
