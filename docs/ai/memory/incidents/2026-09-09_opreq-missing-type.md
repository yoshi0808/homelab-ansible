# Incident: 提供したOPREQ本文にtypeが欠落

日付: 2026-09-09
状態: 解決済み
対象: Coordinatorが提供したストレージ追加調査OPREQ
種別: 動作不具合
原因分類: #製造ミス #テスト不足

## 症状

Yoshinobuが送信wrapperを実行すると、clientが `ansy may only submit OPREQ` で拒否した。登録・通知は行われず、再操作が必要になった。

## 原因

Coordinatorが本文に必須の `type: OPREQ` を入れず、JSON構文検査だけで提供した。

## 修正内容

提供済みの `/tmp/r.json` と `/tmp/storage-followup.json` にtypeを追加した。拒否機構は変更していない。

## 確認方法

clientの送信前検査を読み、両ファイルについてserver-assigned fields拒否検査、補完用コピーのschema検査、関係検査、repoのDLP検査をローカルで実行し全て通過した。修正ファイルの送信は未実施であり、受付成功は未確認。
