# Operations Context: Semaphoreの日次退避物を再構築時に使う

作成日: 2026-08-17
更新日: 2026-09-07

**位置づけ**: `roles/semaphore_db_backup`がSynology NFSへ作る1世代を、
Semaphoreの新規インストール後にproject設定とserver設定の参考として使う際の
範囲を記録する。完全DB復旧の手順ではない。要件の正本は
`docs/ai/reviews/semaphore_db_backup/2026-09-07_011_requirement_api_backup.md`。

値（保存先path、保持世代数）はここへ複製しない。正本は
`roles/semaphore_db_backup/defaults/main.yml`。

## 1. 1世代の中身

保存先の`<世代名>/`には次の2ファイルが揃っている。

| ファイル | 用途 | 位置づけ |
|---|---|---|
| `semaphore_project_backup.json` | 公式`GET /api/project/{project_id}/backup`の応答。template、schedule等のproject設定を含む | 新しいSemaphoreへのproject restoreまたは目視確認用 |
| `config.json` | quoryの`/etc/semaphore/config.json`の写し | 新規インストール後にserver設定を組み直す際の参考用 |

2ファイルは同じ日次世代として原子的に確定するが、両者だけで旧instanceを完全に
再現できるという意味ではない。

## 2. project backup JSON

project JSONはSemaphore自身が公開するAPIから取得する。日次jobは応答がJSON
objectであり、`templates`と`schedules`がarrayであることを確認してから世代を
確定する。

このJSONはproject設定の論理backupであり、少なくとも次は完全DB backupとして
扱わない。

- instance userとAPI token
- task実行履歴とoutput
- secretやSSH private keyの実体
- quoryのOS設定と配備物

新しいSemaphoreへ取り込むときは、対象versionの公式project restore機能を使う。
restore前には、既存projectへの影響とscheduleのactive状態を確認する。復元直後に
カタログreconcileを実行すると、管理対象scheduleはカタログの`active`値へ揃う。

## 3. `config.json`

`config.json`にはDB dialect、listen/TLS設定、通知設定、暗号化関連設定など、
新規インストール後の構成判断に役立つ値がある。一方、製品インストール時に
生成・決定される状態やDB内だけに存在する状態は含まれない。

したがって、退避したファイルを新しいhostへそのまま上書きすることは前提に
しない。新しいhostのpath、証明書、listen設定、権限、導入versionと照合し、
必要な設定を選んで反映するための参考資料として扱う。

内容にはcredential相当の値が含まれうるため、日次退避物ではrootだけが読める
modeで保存し、ログやレビュー文書へ転載しない。

## 4. 新規インストール後の利用順序

1. 対象hostへ、採用するversionのSemaphoreを新規インストールする。
2. 新しいhostの条件と退避した`config.json`を照合し、必要なserver設定を構成する。
3. Semaphoreを起動し、管理者と必要なcredentialを別の正本から作成する。
4. `semaphore_project_backup.json`を公式project restore機能で取り込む。
5. UIまたはAPIでtemplateとscheduleを確認する。scheduleを動かす前にcredential、
   inventory、repository、environmentと実行先到達性を確認する。

この順序は判断点の一覧であり、自動実行するrunbookではない。

## 5. 復元後に確かめること

- templateとscheduleが退避世代の内容と一致する。
- scheduleのactive状態と次回実行時刻が意図どおりである。
- inventory、repository、environment、credentialの参照が解決している。
- test用instanceでは本番credentialを持ち込んでいない。
- 完全DB復旧ではないため、user、token、task履歴、outputが戻らないことを
  欠落やrestore失敗と誤認していない。

想定読者Role: Coordinator = 再構築時に全文確認、Tester = restore検証時に参照、
その他 = 概要のみ。
