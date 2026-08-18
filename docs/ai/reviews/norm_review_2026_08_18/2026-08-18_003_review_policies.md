# Policy群定期見直し — 2026-08-18

## Summary

`docs/ai/policies/*.md` の11本すべてを通読し、各Policyが名指しする実体(playbook名、role名、変数名、script、ADR、Context、schedule)の実在、および実装(tester-gateヘッダ、`roles/semaphore_templates/defaults/main.yml`のカタログ、role defaults)との一致を確認した。

**読了した11本**(全数、以下に一覧):

1. `ansible_test_safety_policy.md`
2. `autonomous_recovery_policy.md`
3. `cert_renew_cloudkey_policy.md`
4. `cert_renew_policy.md`
5. `incident_capture_policy.md`
6. `log_observability_policy.md`
7. `proxmox_backup_restore_verify_policy.md`
8. `proxmox_operations_policy.md`
9. `time_sync_check_policy.md`
10. `ubuntu_vm_patch_policy.md`
11. `unifi_backup_fetch_policy.md`

## 確認した手段(状態を変えない確認)

- 全11本のPolicy本文をRead。
- `grep` / `ls` / `find` によるplaybook・role・script・Context・ADR・Skillファイルの実在確認。
- `grep "^# tester-gate:" playbooks/*.yml` により、各Policyが述べる分類(risk-accepted / check-mode-native / safe-readonly)と実ファイルのヘッダを突合。
- `roles/semaphore_templates/defaults/main.yml` の `semaphore_schedules_catalog` / templateカタログを読み、Policyが述べる実行頻度(週次・月次・曜日)・force既定値と突合。
- 各roleの `defaults/main.yml` を読み、Policyが名指しする変数名(`unifi_backup_keep_generations`等)の実在を確認。
- `AGENTS.md` および `roles/recovery_exec/templates/AGENTS.md.j2` を確認し、AR-069が指す「AGENTS.md」がquory配備側のj2テンプレートであり、repo直下の`AGENTS.md`(開発工程の入口)とは別物であることを確認。
- `docs/ai/roles/operator.md` を読み、Operatorという新しい実行主体が11本のいずれからも前提とされていない(古い主体名の残存もない)ことを確認。
- `docs/ai/adr/001, 003, 004, 005, 007, 009` の各ADR冒頭、`docs/ai/context/operations/*.md` の対象ファイルの実在を確認。

未確認事項(自分で測れなかったもの): 実ホスト(pve1/pve2/authy/sophos-fw/quory)への到達は前提より禁止されているため、Policyが記述するランタイム挙動(閾値判定の実測値など)そのものの実地検証は行っていない。ここではrepo内の静的な整合(名指しの実在・分類の一致)だけを確認した。

## Critical Issues

なし。

## Suggestions

### 1. `cert_renew_policy.md` 変更履歴のplaybook名誤記(v2.3行)

`cert_renew_policy.md` 348行目の変更履歴に `` `deploy_ca_trust.yml` からの中間CA配布を廃止し… `` とあるが、該当playbookは `ca_trust_deploy.yml` である(同文書120行目の§3表では正しく `ca_trust_deploy.yml` と記載されており、リポジトリ内にも `playbooks/ca_trust_deploy.yml` のみが存在し `deploy_ca_trust.yml` は存在しない)。

- 影響範囲: 変更履歴(過去の経緯記述)内の1箇所のみ。現行の許可・禁止・停止条件を定めるCERT番号本文には現れず、規範としての実害はない。
- 実在しないファイル名を検索キーにした場合に「存在しない」という誤った印象を与えうる程度の軽微な誤記。

## What Looks Good

- **playbook名・role名・script名・変数名の名指しはすべて実在を確認できた。** 11本を通じて、存在しないplaybook/role/scriptを規範の対象として名指ししている記述は見つからなかった(唯一の例外は上記Suggestionの変更履歴内誤記で、規範本文ではない)。
- **tester-gateヘッダとPolicy記述の分類は全数一致した。** `ansible_test_safety_policy.md`、`autonomous_recovery_policy.md`、`cert_renew_cloudkey_policy.md`、`cert_renew_policy.md`、`proxmox_backup_restore_verify_policy.md`、`proxmox_operations_policy.md`、`time_sync_check_policy.md`、`ubuntu_vm_patch_policy.md`、`unifi_backup_fetch_policy.md`、`log_observability_policy.md` が言及する各playbookのtester-gate分類(risk-accepted / check-mode-native / safe-readonly / role-guarded)を実headerと突合し、乖離は無かった。
- **Semaphoreスケジュールとの整合。** `cert_renew.yml`の週次・週末(日曜)実行と`force_renew`既定`false`(CERT-024)、`cloudkey_cert_deploy.yml`の月次実行(CCK-017)は、いずれも`semaphore_schedules_catalog`の実クーロン設定と一致した。
- **AR-069の「AGENTS.md」参照は宙ぶらりんではない。** repo直下の`AGENTS.md`(開発工程用)とは別に、quory配備側の`roles/recovery_exec/templates/AGENTS.md.j2`が実在し、AR-069の文脈(Codexが読む指示)に合致する。文書名の同名衝突はあるが、参照先は実在し意味も通る。
- **Operator新設(2026-08)による矛盾は見つからなかった。** 11本のいずれも実行主体としてOperatorへの言及を持たず、Operatorの責務(`docs/ai/roles/operator.md`)と衝突する記述もない。Policy側は「本番実行はquory、判断はYoshinobu、開発はansy」という既存の構図のまま書かれており、Operatorの導入によって古い主体を指す記述に変わった箇所はない。
- **`log_observability_policy.md`のscope拡張(v4.0、metrics系統を包含)は本文全体で一貫している。** UniFi dashboard 7枚・syslog統合dashboard1枚・alert rule 4件という数値(LOG-088)を実ファイル(`roles/grafana_provisioning/files/dashboards/unifi-*.json` 7件、`infra-syslog-all-nodes.json`、`unifi-switch-port-errors.yaml`内のrule 4件)と突合し、一致した。
- **`incident_capture_policy.md`の3段パイプライン(2026-08-03改訂)は退番記録が整合している。** 保持期間90日(IC-043)は`roles/incident_capture/defaults/main.yml`の`incident_capture_retention_days: 90`と一致。転送段(旧`incident_sync`)への言及は変更履歴のみに残り、規範条項(IC番号)には現れない。
- **`tester_mode`・`execpolicy`等、過去に廃止した機構への依存はPolicy本文に残っていない。** 両語の出現箇所はすべて変更履歴内の「廃止した」という記述、またはAR-102のように「安全境界として設計してはならない」という禁止側の言及であり、現行規範がそれらを安全の根拠として使っている箇所はなかった。
- **Policy間の用語衝突は見つからなかった。** `proxmox_operations_policy.md`と`proxmox_backup_restore_verify_policy.md`は同一playbook(`proxmox_backup_restore_verify.yml`)について「詳細規範の正本はBRV側」と明示し二重正本を避けている。`cert_renew_policy.md`と`cert_renew_cloudkey_policy.md`も管轄(CloudKeyは除外)を相互参照で明確に分離している。

## Verdict

Approve(指摘は軽微なSuggestion 1件のみ、規範の許可・禁止・停止条件そのものには影響しない)。

## 指摘ゼロだったPolicy一覧

- `ansible_test_safety_policy.md`
- `autonomous_recovery_policy.md`
- `cert_renew_cloudkey_policy.md`
- `incident_capture_policy.md`
- `log_observability_policy.md`
- `proxmox_backup_restore_verify_policy.md`
- `proxmox_operations_policy.md`
- `time_sync_check_policy.md`
- `ubuntu_vm_patch_policy.md`
- `unifi_backup_fetch_policy.md`

(`cert_renew_policy.md`のみ、変更履歴内の軽微な誤記1件を指摘)

## 未解決事項

- Policyが記述する閾値・タイムアウト等のランタイム挙動そのものの実地検証は行っていない(実ホスト到達禁止のため対象外)。過去のtest_result記録に依拠しており、今回はrepo内の静的整合だけを見た。
- `docs/ai/reviews/policy_standardization/2026-07-25_021_investigation_remaining_policies_rewrite.md`など、各Policyが履歴として参照する案件記録ファイルそのものの内容までは今回読み込んでいない(参照先の実在のみ確認)。
