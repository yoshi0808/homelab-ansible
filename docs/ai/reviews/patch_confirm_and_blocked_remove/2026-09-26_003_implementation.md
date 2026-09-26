# Implementation: patch_confirm_and_blocked_remove

## 変更

- `UN-SAFE:Proxmox patch apply (Manual)` の確認surveyから既定値を除去した。
- `SAFE:Prometheus update check` の操作を `inspect` のみに制限し、2つの手動templateは変更していない。
- dry-runは統合JSONのremove nodeごとに、完全一致の重要package、または同じnodeに同接頭辞installがない重要prefix removeを `BLOCKED` とする。判定はmajorより先に行い、通知・最小reportにpackage名とnodeを出す。apt simulation失敗由来の既存通知本文は分岐で維持した。
- applyの再dry-runにも同じ完全一致/prefix規則を入れ、`BLOCKED` はmode・確認文字列に関係なく停止し、理由へpackage名を含める。
- Semaphore catalogのAC1/AC2を静的に確認するテストを既存task-flowスイートへ追加した。

## 検証

| 確認 | 結果 |
|---|---|
| `python3 roles/semaphore_templates/tests/task_flow/test_catalog_safety.py` | pass |
| `python3 roles/semaphore_templates/tests/task_flow/run_task_flow_tests.py` | pass (11 scenarios) |
| `/tmp/proxmox-important-remove-fixture.yml` のlocalhost実行 | pass: pve2だけのinstallはpve1 removeの置換にならず、完全一致removeもBLOCKED対象 |
| `ansible-playbook --syntax-check playbooks/proxmox_patch_dryrun.yml` | pass |
| `ansible-playbook --syntax-check playbooks/proxmox_patch_apply_node.yml` | pass |
| `python3 scripts/check-doc-consistency.py` | pass |
| `git diff --check` | pass |

## 未確認

- AC4b〜AC4d、AC5〜AC10のentrypoint全体・Slack通知は、実roleが実host上のapt/healthcheck収集を前提にするため、このImplementer roleでは実行していない。実host検証はTesterへ委ねる。
- `pre-commit run --files ...` は `pre-commit: command not found` のため未実行。依存関係の導入はscope外である。
- Semaphore UIでdefaultなしrequired enumが未選択のまま起動拒否されることは、要件どおり配備後にYoshinobuが確認する。

## 差し戻し対応

- 重要remove由来の`BLOCKED`ではCodexのnarrativeを保存せず、最小MDレポートへ`BLOCKED`、package名、nodeを保存するよう、両MD保存taskの条件を排他的にした。
- apply通知の`Phase 4: apply`区画も`blocked_important_remove`時には未実施と表示するようにした。
- dry-runのblocked remove結果をpackage名単位でnode集合へマージして重複を除いた。
- 正規表現で接頭辞を照合する全追加・既存箇所に`regex_escape`を適用した。Tester作成fixtureの丸写し式も同じ形へ同期した。

| 追加検証 | 結果 |
|---|---|
| `bash roles/proxmox_patch_apply_node/tests/compare_dryrun_and_apply.sh` | pass (8 scenarios) |
| dry-run/apply playbookの`--syntax-check` | pass |
| `git diff --check` | pass |
