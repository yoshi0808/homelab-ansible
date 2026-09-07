# requirement: Semaphore日次バックアップを公式APIへ移行する

作成: 2026-09-07 / Coordinator
置換対象: `2026-08-17_001_requirement.md` の日次バックアップ範囲

## 1. 問題定義

現行の日次バックアップは、稼働中のSemaphore SQLite DBを外部`sqlite3`で
`.backup`し、`PRAGMA integrity_check`を成功条件にしている。Semaphore 2.19.12
への更新後、この検査が失敗して日次ジョブが失敗した。一方、Semaphore本体は
稼働しており、画面からproject backup JSONを取得できる。

日次バックアップの目的は完全なinstance DB復旧ではなく、テンプレートと
スケジュールを含むproject設定を、Semaphoreが公開するAPIからJSONで取得する
ことである。既存の`config.json`退避は、新規インストール後の設定参照として
有用なので継続する。

## 2. ゴール

- 公式APIからproject backup JSONを毎日取得する。
- JSONに`templates`と`schedules`が含まれることを、世代確定前に検証する。
- 同じ世代へ`config.json`も保存する。
- 既存の実行ノード選定、NFS確認、原子的確定、30世代保持、Slack通知を維持する。
- 日次ジョブからSemaphore SQLite DBへの直接アクセスをなくす。

## 3. 非ゴール

- `semaphore.db`の取得、整合性検査、修復、完全DB復旧。
- task実行履歴、output、instance user、token、secret実体の復旧。
- `config.json`だけで既存instanceを完全再現できるという保証。
- 今回の障害で報告されたSQLite整合性問題の修復。
- Semaphore上の既存template名、schedule名、cron、保存先directory名の変更。

`config.json`は、製品インストール時に決まる状態やDB内の状態を含まないため、
新規インストール後に設定を組み直す際の参考資料として扱う。

## 4. ユーザーストーリー

運用者として、Semaphoreを新規インストールしてproject設定を再構築する際に、
直近のテンプレートとスケジュールを製品が提供するJSON形式で参照・restore
でき、あわせて当時の`config.json`を設定の参考にしたい。内部DB形式や外部
SQLiteツールには依存したくない。

## 5. 要件

### P0 (Must)

| # | 要件 |
|---|---|
| R1 | project idは固定せず、既存のproject名`homelab-ansible`を`GET /api/projects`で解決する |
| R2 | `GET /api/project/{project_id}/backup`のHTTP 200応答をJSONファイルとして取得する |
| R3 | JSON rootがobjectで、`templates`と`schedules`がarrayであることを確認し、満たさなければ世代を確定しない |
| R4 | 既存のread-only Semaphore API tokenをファイルから読み、token値とAPI応答内容をAnsibleログへ出さない |
| R5 | `config.json`を同じ世代へ保存する。内容をAnsibleログへ出さず、保存先ではrootだけが読めるmodeにする |
| R6 | 1世代はproject backup JSONと`config.json`の2ファイルとし、両方が揃った後だけ原子的に確定する |
| R7 | 稼働中DB、WAL/SHMを含む`/var/lib/semaphore`、外部`sqlite3`、`semaphore projects export`へアクセスしない |
| R8 | NFS保存先と30世代ローテーション、pve1優先/pve2 fallback、成功・失敗Slack通知を維持する |

### P1 (Should)

| # | 要件 |
|---|---|
| R9 | 成功通知にJSON内のtemplate件数とschedule件数を載せる |
| R10 | playbook/role/template/scheduleの既存識別子とNFS directory名を維持し、移行だけでSemaphore objectや保存先を作り直さない |
| R11 | playbook索引と運用文書を新しい復旧範囲へ更新する |

### P2 (Could / Won't now)

| # | 要件 |
|---|---|
| R12 | project JSONの自動restore試験は今回実施しない |
| R13 | `config.json`からの設定自動再構築は今回実装しない |

## 6. 成功指標

- 次の日次実行が終了コード`0`となり、Slack `info/ok`に2ファイルの世代確定と
  template/schedule件数が表示される。
- NFS上の新世代にproject backup JSONと`config.json`だけが存在する。
- roleの実行経路に`sqlite3`、`PRAGMA integrity_check`、`semaphore.db`の読み取りが
  残っていない。
- API/token/NFS/quory/pveの異常時は終了コードが非ゼロとなり、Slack
  `alerts/error`へ通知され、半端な確定世代を残さない。

### 受入条件

**AC1 — 正常な日次バックアップ**

> Given quoryのSemaphore API、既存read-only token、選定pveのNFSが利用可能で
> When `playbooks/semaphore_db_backup.yml`を通常実行すると
> Then 終了コードは`0`で、NFSの新しい世代に
> `semaphore_project_backup.json`と`config.json`が存在し、Slack `info/ok`に
> template件数とschedule件数が表示される。

**AC2 — 必須データがないJSONを確定しない**

> Given API応答がJSON objectでない、または`templates`/`schedules`がarrayでない
> When 日次バックアップを実行すると
> Then 終了コードは非ゼロで、Slack `alerts/error`へ失敗通知し、確定世代を作らない。

**AC3 — API異常を空の成功にしない**

> Given tokenを読めない、認証が拒否される、APIへ到達できない、project名が
> 一意に解決できない、のいずれかで
> When 日次バックアップを実行すると
> Then 終了コードは非ゼロで、Slack `alerts/error`へ失敗通知し、確定世代を作らない。

**AC4 — 2点を1世代として扱う**

> Given project JSON取得後に`config.json`取得またはNFS配置が失敗し
> When cleanupまで終了すると
> Then 終了コードは非ゼロで、確定世代と一時directoryを成功扱いで残さない。

**AC5 — 直接DBアクセスを廃止する**

> Given変更後のrepoと、配備後にSemaphoreが実行する同じGit内容で
> When roleの実行経路を確認すると
> Then SQLite DB、WAL/SHM、`sqlite3`、`PRAGMA integrity_check`を参照するtaskがない。

**AC6 — `config.json`の位置づけ**

> Given生成された2点を復旧資料として扱うとき
> When文書を確認すると
> Then project JSONはproject設定のbackup、`config.json`は新規インストール後の
> 設定参考資料であり、完全復旧を保証しないことが明記されている。

**AC7 — 世代保持**

> Given確定世代が保持数を超えて存在し
> When正常な日次バックアップが完了すると
> Then古い世代だけが削除され、確定後の世代数が30以下となる。

## 7. オープンクエスチョン

なし。取得対象、`config.json`の継続、完全復旧を目的としないことは
Yoshinobuが2026-09-07に確定した。

## 8. タイムライン考慮

- repo変更と検証後、commit/pushはYoshinobuの承認を待つ。
- quoryは次回job開始時にGitから取得するが、初回の通常実行は本番NFSへ世代を
  追加するため、別途Yoshinobuの実行判断を要する。
- 既存scheduleは毎日12:00 JSTのまま維持する。
