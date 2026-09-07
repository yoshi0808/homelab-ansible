# Incident: Semaphore定時バックアップ失敗と自動起票欠落

日付: 2026-09-07
状態: 対応中(repo修正済み、未配備・未実機確認)
対象: `playbooks/semaphore_db_backup.yml` / incident capture pipeline / quory Semaphore
種別: 動作不具合
原因分類: サポート境界外の内部DB依存 / バックアップ要件との不一致

## 症状

2026-09-07 12:00の定時実行で、Semaphore job #1008 (`SEMI-SAFE: Semaphore db backup`) が失敗した。Slack通知で確認できた値は、実行ノード `pve1`、`pve1 reachable: True`、`pve2 reachable: True`、`dest: n/a`、`result: FAILED`、`error: non-zero return code` である。

同日12:06にjob #1008の一次調査完了通知は届いた。自動処理が生成するのはquory上の一次調査成果物までであり、本リポジトリの `docs/ai/memory/incidents/` への昇格は設計上、人または対話セッションが行う。このため、canonical Incidentが自動起票されていないこと自体はtoken枯渇による異常ではない。

read-only調査で、job #1008はquory上で作成したSQLiteスナップショットの `PRAGMA integrity_check` に失敗していたことを確認した。結果は `database disk image is malformed (11)` で、`task` と `task__output` のB-tree/index不整合を報告した。9月6日12:00の前回backup job #997も、同じpage・row・indexを列挙する同一内容で失敗している。

ここでいう「破損」は、外部の直接SQLでSemaphoreの業務データを正しく読めたかではなく、SQLiteファイル内部のB-tree/index整合性が崩れているという物理レベルの判定である。根拠は、(1) `.backup` で作成したsnapshotをSQLite自身の `integrity_check` が具体的なpage・index・rowとともに不整合と判定したこと、(2) 2日連続のsnapshotで同一不整合が再現したことである。Semaphore 2.19.12のプロセス自身も同じSQLiteエラーを記録したが、後述のとおりupgrade中の記録であり、安定稼働後にも製品の通常経路で障害が継続している根拠にはしない。

ただし、`integrity_check` は「物理SQLiteファイルとして整合しているか」しか判定せず、「当該Semaphoreバージョンから復元物を利用できるか」というアプリケーションレベルの整合性は判定しない。現行の定時backupはこの2層を混同しており、後者は同一バージョンの隔離Semaphoreへsnapshotを渡して起動し、API/公式export経路から必要なオブジェクトを読めることで確認する必要がある。

不整合として名指しされたtask row #990は、9月6日08:18 JSTに開始したSemaphore 2.19.8から2.19.12へのupgrade jobである。row #991はその直後に開始したtime sync checkである。9月7日のtemplate reconcile job #1005は本番upgradeではなく、この事象の起点ではない。

一次調査成果物自体はquoryに生成されていたが、内容は `LLM呼び出し終了コード: 1`、`codex invocation returned rc=1 but no response text could be extracted` で、所見・観測事実は空だった。

## 原因

日次jobが失敗した直接原因は、Semaphoreの公式backup APIではなく、外部
`sqlite3`で作ったsnapshotの`PRAGMA integrity_check`を世代確定の必須条件に
していたことである。SQLite不整合が生じた起点は未判明であり、今回の対応では
修復対象にしない。利用者が必要としている日次復旧範囲はtemplateとscheduleを
含むproject設定であり、完全DB復旧ではなかったため、内部DB snapshotを日次jobの
成功条件にした要件自体が過大だった。

quory側Operatorへのread-only調査依頼OPREQ `req-20260907T135733+0900-c3cbcdf1782e859d` に対し、OPRES `req-20260907T142719+0900-cd72d92fe38129c6` を受領した。Operatorは次を確認した。

- Semaphoreサービスは2.19.12でactive/runningである。
- Semaphoreサービス自身もjob #995後のtask-output処理で `database disk image is malformed (11)` を記録している。ただし記録時刻はupgrade/rollback/再upgradeの作業時間帯であり、安定稼働後の通常利用でも同じエラーが継続しているとは判定しない。
- job #990のupgrade、#993のrollback、#995の再upgradeはいずれも成功通知を残した。
- 現行のupgrade成功判定はサービス起動、HTTP、バージョン、オブジェクト数、journal/read-path等を確認するが、SQLite全体の `integrity_check` を含まない。
- upgradeのオンライン事前backupとdetached upgradeのSQLite backupにも、取得後の `integrity_check` がない。
- Semaphore 2.19ではBoltDB supportが廃止された一方、SQLiteは引き続きサポートされている。したがってSQLite snapshot自体を直ちに廃止する根拠にはならないが、業務データの観測を直接SQLへ依存させずAPIへ寄せることと、復元物のアプリケーションレベル検証を追加することは別途必要である。
- Semaphore公式のv2.19.8およびv2.19.12 sourceを比較した。両版とも `modernc.org/sqlite v1.52.0` を使用し、SQLite接続時に `PRAGMA journal_mode = WAL` と `PRAGMA busy_timeout = 5000` を設定する。SQLite採用とWAL化は2.19.12で新たに入った変更ではない。一方、本roleの要件・コメントが前提とする `journal_mode=delete` は現行製品と一致しない。
- 公式v2.19.12 APIは `GET /api/project/{project_id}/backup` と `POST /api/projects/restore` を提供し、UI/CLIのproject JSON backupも同じ製品機能である。公式文書・v2.19.12 sourceには、外部 `/usr/bin/sqlite3` の `.backup` や `PRAGMA integrity_check` をSemaphoreの保証されたbackup契約とする記述は確認できなかった。
- Project JSON backupはproject設定の論理backupであり、instance全体のusers、task実行履歴・output、暗号化されたsecret実体を含む完全なDB backupではない。したがって直接SQLiteアクセスを廃止する場合は、定時backupの復旧範囲をproject設定へ縮めるか、Semaphoreを正常停止してDBファイルを取得する別経路を設けるかを要求として決め直す必要がある。
- migration statusとLLM終了コード1の具体理由は未確認である。成果物からtoken/usage枯渇とは断定できない。
- 調査中に修復、再実行、停止、設定変更その他の状態変更は行っていない。

Semaphoreサービス自身が同エラーを記録したという根拠を確定するため、該当journal行の原文・時刻・処理内容だけを求める追加OPREQ `req-20260907T144733+0900-65d337dfdf5e4cc5` を提出し、OPRES `req-20260907T144949+0900-88bd9f9cd1d5161e` を受領した。Semaphoreサービスのjournalには、2026-09-06 08:53:33.097464 JSTと09:02:28.387418 JSTの2回、`database disk image is malformed (11)` と `Bad request. Cannot get task output from database` が記録されていた。最初の記録より前の08:51:01 JSTには `Server is running` が記録されている。この08時台から09時台はupgrade/rollback/再upgradeの作業時間帯である。その後、9月6日12:00の定時backup job #997と、最初にSlackスクリーンショットで確認した9月7日12:00の定時backup job #1008が、2日連続で同一内容のintegrity検査に失敗した。追加調査、修復、再実行は行われていない。

## 修正内容

`docs/ai/reviews/semaphore_db_backup/2026-09-07_011_requirement_api_backup.md`
で日次backupの範囲を改定した。

- project名を`GET /api/projects`で解決し、公式
  `GET /api/project/{project_id}/backup`のJSONを取得する。
- JSON rootと`templates`/`schedules`の型を検証してから世代を確定する。
- 既存の`config.json`退避は、新規インストール後の設定参考資料として継続する。
- `semaphore.db`、外部`sqlite3`、`PRAGMA integrity_check`、製品CLI exportへの依存を
  日次jobから削除する。
- pve実行ノード選定、NFS確認、2点の原子的確定、30世代保持、Slack通知は維持する。

`config.json`とproject JSONだけでinstanceを完全復旧できるとは扱わない。user、
token、task履歴/output、secret実体、製品インストール時に決まる状態は対象外である。

## 確認方法

- `ansible-playbook --syntax-check playbooks/semaphore_db_backup.yml`: PASS。
- `ansible-lint roles/semaphore_db_backup/tasks/main.yml
  roles/semaphore_db_backup/defaults/main.yml`: failure/warning 0。
- loopbackのHTTP fixtureで、project一覧からのID解決、backup endpointからのJSON
  保存、`templates`/`schedules`型検証を同じAnsible式で実行: PASS。
- `schedules`を文字列にしたnegative fixtureが型検証でfailすることを確認: PASS。
- 本番quory/NFSへの通常実行は未実施。配備後のjob終了コード、NFS上の2ファイル、
  Slack通知のtemplate/schedule件数を確認して解決済みへ移す。
