#!/usr/bin/env bash
# tester_mode 不変条件 lint
#
# 不変条件: どの playbook も `-e tester_mode=true` 付きで実行した場合、
# 対象ホストの実変更・外部副作用(Slack 通知含む)を起こさないこと。
#
# playbooks/ 配下の全 playbook が以下のいずれかを満たすことを機械チェックする:
#   1. 実ゲートを持つ: tester_gate role の include("name: tester_gate" 行)がある
#      (単なる tester_mode 文字列やコメントでは通らない — 2026-07-02_008_review suggestion 対応)
#   2. SAFE 宣言マーカー   : "# tester-gate: safe-readonly — <理由>"
#      (read-only 収集のみ。冪等な収集スクリプト配置とローカルレポート出力は許容)
#   3. role 側ガード宣言   : "# tester-gate: role-guarded — <理由>"
#      (副作用が通知のみで、common_slack notify.yml の tester_mode ガードで抑止される)
#   4. role 内ゲート宣言   : "# tester-gate: gated-in-role — <ゲートを持つ role のパス>"
#      (ゲートが playbook ではなく role のタスク先頭にある)
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fail=0
count=0

for pb in "$repo_root"/playbooks/*.yml; do
  count=$((count + 1))
  if grep -Eq '^[[:space:]]*name: tester_gate[[:space:]]*$' "$pb"; then
    continue
  fi
  if grep -Eq '^# tester-gate: (safe-readonly|role-guarded|gated-in-role)' "$pb"; then
    continue
  fi
  echo "ERROR: playbooks/$(basename "$pb"): tester_gate の include も '# tester-gate:' マーカーもありません"
  fail=1
done

if [[ $fail -ne 0 ]]; then
  cat <<'EOF'
tester_mode 不変条件(実変更・外部副作用ゼロ)を担保できません。以下のいずれかで対応してください:
  - 変更系 playbook       : tester_gate role の include を危険操作の前に追加する
  - read-only playbook    : ヘッダに "# tester-gate: safe-readonly — <理由>" を追加する
  - 通知のみの playbook   : ヘッダに "# tester-gate: role-guarded — <理由>" を追加する
  - ゲートが role 内にある: ヘッダに "# tester-gate: gated-in-role — <role パス>" を追加する
詳細: docs/ai/prompts/core.md のテスト工程(tester)を参照。
EOF
  exit 1
fi

echo "[tester-gate-lint] OK (${count} playbooks)"
