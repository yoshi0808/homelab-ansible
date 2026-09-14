# 配備と本番初実行の観測

日付: 2026-09-14

## 配備

| ジョブ | template | モード | 結果 |
|---|---|---|---|
| #1099 / #1100 | Dev investigate setup / Recovery exec setup | **check(native Dry Run ON)** | success。ただし**配備物は変わっていない** |
| #1101 / #1102 | 同上 | apply | success。配備完了 |

**この2本のplaybookはcheck modeでは何も配らない。** `roles/dev_investigate/tasks/main.yml` の各タスクが `when: not ansible_check_mode` を持つため、check modeでは Gathering Facts 以外の全タスクがskipする(#1099は `ok=1 changed=0 skipped=9`)。**「先に`--check`で差分を読む」という運びは、このplaybookには効かない** — 差分が出ないのではなく、検査そのものが行われない。`semaphore_templates_setup`(check-mode-native、read-onlyは常に実行しwriteだけをゲートする)と混同しないこと。**Coordinatorが#1099/#1100の前にこの2本を同じ運びで案内したのは誤りだった。**

## AC7(配備後のhash一致)— PASS

`deployed-hash` とrepo現物の `sha256sum` が一致した。

| 対象 | hash |
|---|---|
| `/usr/local/sbin/recovery-investigate-dispatch-quory.sh` | `e0da1355…` |
| `/usr/local/bin/homelab-semaphore-query` | `494979ba…` |

#1099/#1100直後は両方とも `HEAD~1` の値と完全一致しており、これが「配られていない」ことの証拠になった。

**class P / G のdispatchは照合できない。** `deployed-hash` の対応表に無く、ansyからpve / authy / monnieへの到達手段も無い。配備されたことは #1102 の成功以上には確かめられない。

## 本番での初実行

| 入力(quory) | 観測 |
|---|---|
| `pkg-list 'nvme*'` | `nvme-cli	2.16-1	ii`、rc=0 |
| `pkg-list`(引数なし) | 832行、rc=0 |
| `pkg-list 'a;b'` | `denied: invalid pattern for pkg-list`、rc=1 |
| `semaphore-query schedule-list 200` | 24件。`{"active": true, "cron_format": "15 8 15 * *", "id": 25, "name": "SEMI-SAFE: Quory health monthly", "template_id": 60, ...}` |

**schedule-listで、同日に登録したscheduleが本番に入っていること(`active: true`、cron一致)を開発側から初めて読み返せた。** 起案の動機のうち「入ったか・有効か・cronは何か」はこれで満たされた。次回実行時刻はAPIが返さないため、引き続きUIでのみ確認できる。

## 未達

- **AC7のドリフト検査側**: 翌日(2026-09-15 00:40)の日次検査で差分が出ないこと。未観測。
- 実ホストの `dpkg-query` は quory でのみ確認した(pve / authy / monnie では実行手段が無い)。
