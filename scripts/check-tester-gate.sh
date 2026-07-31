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
#   - risk-accepted      : 常に本実行してよいと人間が判断。dry-run を持たず、
#                          --check を渡されたら停止する(TS-030)
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
  if ! grep -Eq '^# tester-gate: (safe-readonly|role-guarded|risk-accepted|check-mode-native|dry-run-aware)' "$pb"; then
    echo "ERROR: playbooks/$(basename "$pb"): '# tester-gate:' マーカーがありません"
    fail=1
    continue
  fi

  # risk-accepted は --check を dry-run として提供しない(TS-030)。宣言だけでは
  # 何も止まらず、check_mode: false により --check がそのまま本適用になるため、
  # 停止 assert の存在を機械的に要求する(2026-07-31 Incident: subagent が
  # --check 付きで実配備した)。
  #
  # これは床であって網羅ではない。TS-030 は「変更を行う各 play に置く」ことを
  # 求めるが、どの play が変更を行うかはこのスクリプトからは判定できない。
  # play 単位の充足はレビュー工程が見る。
  if grep -Eq '^# tester-gate: risk-accepted' "$pb"; then
    if ! grep -Eq '^[[:space:]]*that:[[:space:]]*not[[:space:]]*\(?[[:space:]]*ansible_check_mode' "$pb"; then
      echo "ERROR: playbooks/$(basename "$pb"): risk-accepted なのに --check 停止 assert がありません"
      fail=1
    fi
  fi
done

if [[ $fail -ne 0 ]]; then
  cat <<'EOF'
全 playbook はヘッダに `# tester-gate: <種別> — <理由>` マーカーが必要です。
種別: safe-readonly / role-guarded / risk-accepted / check-mode-native / dry-run-aware

risk-accepted は加えて、pre_tasks に `ansible_check_mode` が真なら停止する
assert(`that: not (ansible_check_mode | bool)`)が必要です。--check で
dry-run にならず本適用してしまう経路を残さないためです(TS-030)。
--check で安全に検証できるようにしたなら、assert を足すのではなく
分類そのものを check-mode-native へ変えてください(TS-032)。

詳細: docs/ai/policies/ansible_test_safety_policy.md を参照。
EOF
  exit 1
fi

echo "[tester-gate-lint] OK (${count} playbooks)"
