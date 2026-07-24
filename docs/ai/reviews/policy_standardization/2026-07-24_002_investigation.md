# Policy構造標準化 調査記録

日付: 2026-07-24

担当: implementer2

成果物: `docs/ai/policy-migration-map.md`

## 1. 調査目的と境界

`2026-07-24_001_requirement.md` のP0/P1/P2に基づき、10文書を標準8セクションへ対応付け、6つの目的別論理groupを実playbook/roleへ突合し、`proxmox_patch_policy.md` のPolicy範囲超過候補を特定した。

実施したのは構造評価のみである。Policy記述とコードの意味的整合性、Policy本文の是正、playbook/role変更、実機確認は対象外とした。既存の他者変更には触れていない。

## 2. 参照した正本

- requirement: `docs/ai/reviews/policy_standardization/2026-07-24_001_requirement.md`
- 共通原則・境界: `docs/ai/core.md`、`docs/ai/context-classification.md`
- 形式: `docs/ai/core-migration-map.md`
- Policy 9本: `docs/ai/policies/*_policy.md` 全文
- Repository Context: `docs/ai/context/ansible/playbook-map.md`、`role-map.md`
- 実装突合: `playbooks/*.yml`、対象 `roles/*/tasks`、`defaults`

行番号は `nl -ba` により現行ファイルから採取した。見出し数は `rg -n '^## '`、文書行数は `wc -l` で確認した。

## 3. 調査結果

### 3.1 対象文書と標準セル

- 対象は `core.md` 1本とPolicy 9本の計10文書。
- 標準は目的、対象と実行範囲、対応するPlaybook、判断軸、ライフサイクル・処理フロー、通知方針、制約・禁止事項、変更履歴の8セクション。
- `policy-migration-map.md` の単一対応表に10行×8標準セルを収録した。
- 非対応は「未整備」と「該当なし」を分けた。前者は業務上必要だが構造・記述がないもの、後者は文書種別または業務上不要なもの。
- `core.md` は全Role共通原則であり、対応Playbook、個別ライフサイクル、個別通知は該当なし。これらは欠落数に含めない。

### 3.2 requirement記載と現行実測の差

変更履歴見出しはPolicy 9本中5本に存在した。存在するのは `cert_renew_cloudkey`、`cert_renew`、`log_observability`、`time_sync_check`、`unifi_backup_fetch`。欠落は4本である。requirementの「4/9本にしかない」は現行実測と一致しないため、索引では5/9を正とした。

標準名の独立した「対応するPlaybook」見出しは6/9本に存在し、標準名がないのは `autonomous_recovery`、`proxmox_patch`、`ubuntu_vm_patch` の3本だった。`proxmox_patch` と `ubuntu_vm_patch` は別名見出しが標準内容を実質的に担うため、索引セルでは「対応（別名見出し／標準名未統一）」とした。`autonomous_recovery` は入口が複数節へ散在し、標準内容がまとまらないため「未整備」とした。

### 3.3 判断軸

明示的なStatus/Urgency節が実在するのは `proxmox_patch_policy.md`。他8 Policyには、鮮度と取得・確定・cleanup成否、時刻offset、証明書期限、配信検証、restore正常性、cutover gate、recovery ladderとmute / global pause、reboot/更新判定という概念相当の判断軸が存在した。単なるデータ項目と続行・停止の規範を区別して索引へ記録した。

### 3.4 6つの論理group

- 健康監視は4つの専用healthcheck入口/roleを追加して条件付き妥当とした。
- アプリ・パッケージ更新は `ubuntu_vm_full_upgrade` を明示追加し、`ubuntu_nightly` はreboot補助として分離表示した。主機能roleは `codex_update_check`、`prometheus_update_check`、`ubuntu_vm_full_upgrade`、`radius_healthcheck`、`monitoring_healthcheck` と実名列挙した。
- Proxmox patchは複数安全度と退避・復帰を持つため独立維持が妥当。
- 構成ドリフト検知は不成立。`systemd_timers` は構成配備、`proxmox_snapshot_check` は状態・鮮度診断で共通目的がない。
- リソース・容量管理は名称修正が必要。`sophos_trim` はtrim実行であり容量測定ではない。現行の容量閾値を担う関連roleは `proxmox_healthcheck`、`monitoring_healthcheck`、`radius_healthcheck` と実名列挙した。
- `serial_getty_mask.yml` は単一目的がplaybookに閉じており、Policyなしを維持する。

6案は全Policyの分類ではないため、証明書/CA、backup/restore、observability、autonomous recovery、time syncを非対象系統として別掲した。

### 3.5 `proxmox_patch_policy.md` の境界

Policyへ残すのは、適用可否、重要コンポーネント、Status/Urgency、実行条件、停止条件、順序上の安全条件、禁止事項である。次を範囲超過候補として行単位で分類した。

- System/Repository Context: ノード現状、inventory/タグ実装、playbook/role詳細、実行端末の現状。
- Operations Context/runbook: 仮時刻、逐次操作、retry調整例、Mode別標準手順、§18.2-§18.4のノード別復旧手順・再構築情報。§18.1のOS rollback禁止・再インストール原則はPolicy核として残す。
- Skill/実装契約: changelogコマンド、JSON例、Codex CLI入出力・責務表。
- Issue/Decision/test plan: Sophos移行タイミング、今後の実装順序、初期品質テスト。

同じsectionにPolicy核と範囲超過が混在する箇所は、section全体を機械移動せず「移す行」と「残す核」を併記した。

## 4. 機械確認

確認結果:

- PASS: `documents=10`、対象文書名10件が対応表に各1回ある。
- PASS: `standard_sections=8`、`standard_cells=80`、`matrix_bad=0`。matrixは10行、各行は文書名+8セルの9列である。
- PASS: `logical_groups=6`、`group_bad=0`。6論理groupが各1行あり、判定・playbook・role・差分が空でない。
- PASS: `empty_table_cells=0`。2成果物のMarkdown表に空セルがない。
- PASS: `ipv4_literals=0`。2成果物にIPv4 literalがない。
- PASS: review指定の根拠行を原文で再照合し、`context-classification.md` L31-48、Proxmox §11.6 / §16.8.3 / §18 / §20、Unifi §4、autonomous recovery §7の見出し・内容と索引参照が一致する。
- PASS: `git diff --check`、および未追跡の2成果物に対する `git diff --no-index --check /dev/null <file>` は空白エラーを出力しない。

## 5. 未実施・次工程

- 個別Policyの書換、分割、統合は未実施。
- Policyとコードの意味的整合レビューは未実施。
- 書換優先順位は提案であり、採否と個別requirementはTech Lead/Coordinatorが決める。
