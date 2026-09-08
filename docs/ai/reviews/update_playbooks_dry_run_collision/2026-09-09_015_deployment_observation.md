# 配備観測: update playbooks dry_run collision

日付: 2026-09-09
実施主体: Yoshinobu（Semaphore起動）/ Coordinator（forced command readback）

## Reconcile

| job | mode | 結果 | 観測 |
|---|---|---|---|
| #1028 | Semaphore native Dry Run | success | template 5件、schedule 2件だけを変更として検出。新規template/scheduleは0件、schedule preflightは成功、API書込みは0件 |
| #1029 | 通常実行 | success | template 5件を更新。schedule 2件を更新し、各PUT直後GETのexact verifyに成功。scheduleの見送り0件、管理外0件 |

template側の既知の管理外1件は、catalog自身を起動する
`SEMI-SAFE: Semaphore templates setup`（id=37）であり、削除されていない。

## Readback（AC9）

`semaphore-query template-list 200`のAPI応答から対象id 24〜28を抽出し、次を確認した。

- Ubuntu 2 templateは`ubuntu_vm_full_upgrade_operation` enum（`inspect|apply`）を持ち、
  旧`dry_run` Surveyを持たない。apply templateの`node`とconfirmationは維持。
- Prometheus 3 templateは`prometheus_update_check_operation` enum
  （`inspect|update|rollback`）を持ち、旧`dry_run` / `rollback` Surveyを持たない。
  rollback templateの`rollback_to`は維持。
- playbook、template名、argumentsはcatalogどおりである。

scheduleはjob #1029内でPUT直後に個別GETされ、exact verifyが2件とも成功した。

- Ubuntu月次schedule: `operation=inspect`、native `params.dry_run=false`、cron / activeを維持。
- Prometheus週次schedule: `operation=inspect`、native `params.dry_run=false`、
  `debug_level=4`、cron / activeを維持。

## 通常inspectionと通知

| job | template | 結果 |
|---|---|---|
| #1030 | `SEMI-SAFE: Ubuntu vm full upgrade (dry-run)` | success。4 hostでinspectionを行い、`Manual apply`はskip。Slack送信成功 |
| #1031 | `SAFE: Prometheus update check (check)` | success。summaryは`operation=inspect`、update / rollbackはskip。Slack送信成功 |

通常inspectionのためSemaphore native Dry Runは使用していない。job出力の`changed=1`（Ubuntu各host）は
report / notification evidenceの保存によるもので、upgrade/rebootの変更taskには到達していない。

## 結論と残存事項

AC9と、Step 5の通常inspection / Slack通知観測を満たした。実update、rollback、rebootは要件どおり
実施していない。

Ubuntu inspection template名の`(dry-run)`は既存identityを維持するため残っており、native Dry Runを
OFFにして通常inspectionを行う現在の操作と見た目が紛らわしいことを、今回Yoshinobuが実操作時に
確認した。機能上は`operation=inspect`で変更経路を閉じているが、UI名称の改善は別案件候補とする。
