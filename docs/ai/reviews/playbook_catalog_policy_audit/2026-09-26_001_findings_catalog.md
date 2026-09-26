# 第1段: playbook一覧・Semaphoreカタログと実物の差異

作成: 2026-09-26 / Coordinator

## 範囲と、既に機械検査されているもの

- `playbooks/README.md`(62行)と `playbooks/*.yml`(62本)
- `roles/semaphore_templates/defaults/main.yml` の `semaphore_templates_catalog`(57件)と `semaphore_templates_orphan_baseline`

次の3つはこの段で照合していない。**既に機械検査が毎回見ている**ためである。

| 何を | どこが見ている |
|---|---|
| READMEの「対象」列 ↔ playの `hosts:` | `scripts/check-doc-consistency.py` check1(pre-commit) |
| READMEの `tester-gate` 列 ↔ ヘッダの `# tester-gate:` | 同上 |
| Semaphoreに実際に登録されているもの ↔ repoのカタログ | `playbooks/deployment_drift_check.yml` のSemaphore API突合(R9-a、日次) |

## 照合して一致したもの

- READMEの行とplaybookファイルは1対1(過不足なし)
- READMEの「主な role / 実装」列: 名前の挙がったroleはすべて実際に使われている。挙がっていないroleは補助role(`proxmox_exec_node` / `proxmox_reachable_nodes` など)だけ
- カタログの57件はすべて実在するplaybookを指す
- カタログに無いplaybook12本は、いずれもSemaphore以外の経路で動くとREADMEかヘッダに書かれている(systemd timer、他スクリプトからの起動、ansy専用、一度きりの後始末、sandbox専用)。`semaphore_templates_setup.yml` は orphan baseline として意図的に外されている
- 分類名(`class`)と表示名の接頭辞が食い違う2件(`SEMI-SAFE: Proxmox patch dry-run`、`UNSAFE:Prometheus rollback(Manual)`)は、改名が非対応のため旧名のまま転記していると、カタログのコメントに理由がある
- `class: SAFE` と `tester-gate: risk-accepted` の組(`proxmox_backup_restore_verify.yml`)は `class_reason` とコメントに理由がある(2026-08-04 Yoshinobu判断)

## findings

### F1-1(中) `SAFE:Prometheus update check` の選択肢から update / rollback を実行できる

- `roles/semaphore_templates/defaults/main.yml:311-316` — `class: SAFE`、`variant: check`、表示名 `SAFE:Prometheus update check`。surveyの `prometheus_update_check_operation` は `values: [inspect, update, rollback]`(既定 `inspect`)
- `playbooks/prometheus_update_check.yml:54-60` — operation を `inspect` / `update` / `rollback` のいずれかに制限するassertだけで、updateやrollbackに確認の入力は求めない
- **起きること**: SAFEのボタンで選択肢を `update` に変えて実行すると、monnieのPrometheusのバイナリが更新される。区分がSAFEであること、選択肢が並んでいることの両方が誤操作を招く
- 比較: `UN-SAFE: Ubuntu vm full upgrade (Manual)` は `apply` に `node` と `ubuntu_vm_full_upgrade_confirm` の一致を要求している(`roles/ubuntu_vm_full_upgrade/tasks/main.yml:62-64`)。月次dry-runのテンプレート(`:283-288`)も選択肢に `apply` を持つが、confirmが無いため適用には進まない

### F1-2(低) `dev_investigate_setup.yml` のチェック数が3か所で違う

- `playbooks/dev_investigate_setup.yml:6` — 「the 20 read-only checks」
- `playbooks/README.md:103` — 「25本のread専用チェック」
- `roles/dev_investigate/files/recovery-investigate-dispatch-quory.sh:127-421` — Operator Request Channelの4本を除くcaseラベルを数えると26(`bundle-list` 〜 `forced-command-keys`)。**数え方は目視のcaseラベルで、入れ子のサブコマンドの扱いは確かめていない**
- 数を書く箇所が複数あり、追加のたびにずれる。数を書かずに一覧の正本(`docs/ai/reviews/dev_prod_boundary/2026-08-03_008_phase3_check_catalog.md`)を指す形にするのが案

### F1-3(低) READMEの `grafana_provisioning.yml` の行で列が1つ足りない

- `playbooks/README.md` 「監視・ログ基盤」表の `grafana_provisioning.yml` 行は4セルで終わり、「主な role / 実装」列が無い(他の行は5セル)
