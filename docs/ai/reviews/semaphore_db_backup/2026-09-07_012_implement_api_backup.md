# Semaphore日次バックアップ API移行 実装記録

日付: 2026-09-07
担当: Coordinator（作る側）
要求: `2026-09-07_011_requirement_api_backup.md`

## 結果

日次backupのquory側取得経路を、外部SQLite snapshotと製品CLI exportから
Semaphore公式project backup REST APIへ変更した。`config.json`の退避、NFSへの
原子的な世代確定、30世代保持、pve実行ノードfallback、Slack通知は維持した。

## 実装内容

- `roles/semaphore_db_backup/defaults/main.yml`
  - SQLite DB/binaryとSemaphore CLI binaryの変数を削除。
  - 固定API URLと既存read-only token pathを追加。
- `roles/semaphore_db_backup/tasks/main.yml`
  - `GET /api/projects`で`homelab-ansible`を一意に解決。
  - `GET /api/project/{project_id}/backup`を
    `semaphore_project_backup.json`へ保存。
  - JSON root、`templates`、`schedules`の型を確定前に検証。
  - token、Authorization header、API responseを`no_log`で保護し、利用後に
    host fact上の値を空にする。
  - 世代の成果物をproject backup JSONと`config.json`の2点へ変更。
  - SQLite snapshot、`PRAGMA integrity_check`、CLI exportを削除。
- `playbooks/semaphore_db_backup.yml`
  - 実行説明と成功summaryを2点backupへ更新。
  - template/schedule件数を成功通知へ追加。
- `playbooks/README.md`、`roles/semaphore_templates/defaults/main.yml`、
  `docs/ai/context/operations/semaphore-db-restore.md`
  - 日次backupと復旧範囲を更新。既存template/schedule識別子、cron、NFS directory
    名は互換性のため変更していない。

## 検証

| 検証 | 結果 |
|---|---|
| `git diff --check` | PASS |
| `ansible-playbook --syntax-check playbooks/semaphore_db_backup.yml` | PASS（動的group未生成warningのみ） |
| 変更roleの`ansible-lint` | PASS（0 failure / 0 warning） |
| loopback HTTP fixtureによるAPI一覧→ID解決→backup JSON保存→型検証 | PASS |
| `schedules`がarrayでないnegative fixture | 期待どおり検証failure |

playbook全体の`ansible-lint`には、既存の`proxmox_exec_node`、`common_slack`等に
由来する19件が残る。変更した`semaphore_db_backup` role単体はproduction profileを
通過しており、本変更で増えた指摘はない。

## 未実施

- quory/NFSへ書き込む通常実行（`risk-accepted`）。
- 実tokenでのproject backup endpoint疎通と、実世代2ファイルの確認。
- commit / push / Semaphore job実行。

これらはYoshinobuの次の実行判断後に行う。
