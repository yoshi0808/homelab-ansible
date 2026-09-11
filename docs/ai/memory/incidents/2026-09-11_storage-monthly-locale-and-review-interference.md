# Incident: 月次ストレージ日時解析のlocale依存と検証中の差分変更

日付: 2026-09-11
状態: 調査中
対象: proxmox_storage_monthly / Coordinatorの検証工程
種別: 未遂

## 症状

009 Tester記録で、日本語localeのAnsible moduleが英語のscrub日時をstrptimeで解釈できず、正常fixtureもUNKNOWN/収集失敗になることを確認。Coordinator側のC系localeでの成功だけでは検出できなかった。
同時にCoordinatorが007指摘に対応する3テストを追加し、走行中のReviewer/Testerが対象の変化を検知して停止した。変更者はCoordinatorであり、他者の変更の削除・復元はしていない。

## 対応

日時解析をlocale非依存の月名対応と数値datetime構築へ変更。C/日本語localeの回帰テストを追加し、再レビュー・再テストでは差分を固定する。本番のscrub、cron、Notion、Slackへは変更・送信していない。

## 確認

根拠は案件007/009と006の対応記録。独立再検証は未了。
