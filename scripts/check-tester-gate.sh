#!/usr/bin/env bash
# playbook check_mode 安全分類 lint(旧 tester_mode 不変条件 lint)
#
# playbooks/ 配下の全 playbook が、ヘッダに以下いずれかの `# tester-gate:` マーカーを
# 持つことを機械チェックする(単なる tester_mode 文字列やコメントでは通らない)。
# tester_gate role は 2026-07-06〜07 の ansible_check_mode 移行で廃止済み。
# 各マーカーの意味は docs/ai/policies/ansible_test_safety_policy.md を参照:
#   - safe-readonly     : read-only 収集のみ。ゲート不要
#   - role-guarded       : 副作用が Slack 通知のみで、common_slack notify.yml の
#                          skip_notifications ガードで抑止される
#   - risk-accepted      : 常に本実行してよいと人間が判断(--check の有無で挙動不変)
#   - check-mode-native  : read-only 部分は常に本実行し、破壊的操作を
#                          ansible_check_mode でゲート
#   - dry-run-aware      : 破壊的コマンド自体を ansible_check_mode 下でネイティブの
#                          dry-run 引数に差し替え
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fail=0
count=0

for pb in "$repo_root"/playbooks/*.yml; do
  count=$((count + 1))
  if grep -Eq '^# tester-gate: (safe-readonly|role-guarded|risk-accepted|check-mode-native|dry-run-aware)' "$pb"; then
    continue
  fi
  echo "ERROR: playbooks/$(basename "$pb"): '# tester-gate:' マーカーがありません"
  fail=1
done

if [[ $fail -ne 0 ]]; then
  cat <<'EOF'
全 playbook はヘッダに `# tester-gate: <種別> — <理由>` マーカーが必要です。
種別: safe-readonly / role-guarded / risk-accepted / check-mode-native / dry-run-aware
詳細: docs/ai/policies/ansible_test_safety_policy.md を参照。
EOF
  exit 1
fi

echo "[tester-gate-lint] OK (${count} playbooks)"
