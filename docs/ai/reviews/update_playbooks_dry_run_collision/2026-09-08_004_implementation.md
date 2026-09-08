# 実装記録: update playbooks dry_run collision

## 変更対象

- `playbooks/ubuntu_vm_full_upgrade.yml`
- `playbooks/prometheus_update_check.yml`
- `roles/ubuntu_vm_full_upgrade/tasks/main.yml`
- `roles/prometheus_update_check/defaults/main.yml`
- `roles/prometheus_update_check/tasks/main.yml`
- `roles/semaphore_templates/defaults/main.yml`（5 template、2 schedule）
- `playbooks/README.md`
- `docs/ai/policies/ubuntu_vm_patch_policy.md`
- `docs/ai/context/operations/ubuntu-vm-patch.md`
- `docs/ai/status.md`

## 実装結果 / AC対応

- Ubuntu は `ubuntu_vm_full_upgrade_operation=inspect|apply`、Prometheus は `prometheus_update_check_operation=inspect|update|rollback` を必須化。
- 旧 `dry_run`（およびPrometheus旧 `rollback`）は値に関係なく `tags: [always]` のfail-closed guardで拒否。
- operation未指定・未知値もfail-closed。update/rollbackの変更経路は native `--check` でも停止し、Slack送信は既存notify guardに委譲。
- Semaphore 5 templateのsurveyと2 scheduleのenvironmentをnamespaced operationへ変更。scheduleの `params.dry_run=false` はSemaphore native check modeとして維持。
- Policy、Operations Context、README/statusの記述を新しい入力契約へ整合。

## 自己検証

| コマンド | rc | 結果 |
|---|---:|---|
| `ansible-playbook --syntax-check playbooks/ubuntu_vm_full_upgrade.yml -i localhost, -c local` | 0 | 構文OK（対象inventory不在warningのみ） |
| `ansible-playbook --syntax-check playbooks/prometheus_update_check.yml -i localhost, -c local` | 0 | 構文OK（対象inventory不在warningのみ） |
| `git diff --check` | 0 | whitespaceエラーなし |
| `ansible-playbook playbooks/prometheus_update_check.yml -i localhost, -c local -e prometheus_update_check_operation=bogus` | 2 | unknown operationをalways guardで拒否、変更経路未到達 |

実ホスト、quory、通常update/rollback/reboot、production Slack、commit/pushは実行していない。localhostでの本番経路実行および実artifact取得は未検証（安全境界上の未検証事項）。

## 2026-09-09 差し戻し対応

- Ubuntu Semaphore identity（`variant: dry-run`、既存legacy_name、schedule name/template）を復元し、Survey/environmentのみoperation化。全operation Surveyへ `type: enum` を追加。
- Prometheus入口を `gather_facts: false` とし、legacy/operation guard後に明示 `setup` を実行。effective operation factへ正規化し、全分岐・summary・通知で使用。
- Slack本文へoperationを追加し、liveな旧dry_run説明、Policy UV-039、履歴/statusをoperation/native check表現へ更新。statusは配備/readback/通知観測待ちのNowへ移動。
- 再検証: `ansible-playbook --syntax-check playbooks/ubuntu_vm_full_upgrade.yml -i localhost, -c local` rc=0、同Prometheus rc=0、`git diff --check` rc=0。実Semaphore reconcile/readback、通常inspect通知、実host経路は未検証。

## 2026-09-09 再差し戻し対応

- Policy UV-070/076、変更履歴（2026-09-09）、catalog第2バッチ説明、Prometheus/Ubuntuのlive task説明をinspect/apply/update/rollbackとnative checkの二軸へ修正。identity保持用の旧表記、reject-only guard、native `params.dry_run`は保持。
- statusの案件行を実際の`## Now`節へ移動。rollback_available通知を「inspect/check」からnative checkのみの表現へ修正。
- 再検証: Ubuntu/Prometheus syntax-check rc=0、`python3 scripts/check-doc-consistency.py` rc=0、`git diff --check` rc=0。実ホスト・quory・Slack・commit/push未実行。

## 2026-09-09 最終限定修正

- `docs/ai/status.md`の隣接する将来案件を、scheduled `operation=inspect`とmanual
  `operation=apply|update|rollback`の現行契約へ更新した。
- Prometheusの`rollback_available`通知をnative check modeだけの表現へ限定した。
- Semaphore scheduleの時刻表コメントとUbuntu healthcheckの現在経路説明を`inspect` /
  `inspection`へ更新した。identity保持に必要な`variant: dry-run`、legacy name、schedule
  name/template、reject-only guard、Semaphore native `params.dry_run`は変更していない。
- 最終検証: `python3 scripts/check-doc-consistency.py` rc=0、`git diff --check` rc=0。
  実ホスト・quory・Slack・commit/pushは実行していない。
