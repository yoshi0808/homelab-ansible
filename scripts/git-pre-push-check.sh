#!/usr/bin/env bash
set -euo pipefail

echo "[pre-push] running full gitleaks scan..."

if command -v gitleaks >/dev/null 2>&1; then
  gitleaks git --verbose
else
  echo "ERROR: gitleaks not found"
  exit 1
fi

echo "[pre-push] OK"
