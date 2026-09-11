# Incident: 月次ストレージ日時解析のlocale依存と検証中の差分変更

日付: 2026-09-11
状態: 解決済み
対象: proxmox_storage_monthly / Coordinatorの検証工程
種別: 未遂
原因分類: #製造ミス #テスト不足 #運用考慮ミス

## 症状

009 Tester記録で、日本語localeのAnsible moduleが英語のscrub日時をstrptimeで解釈できず、正常fixtureもUNKNOWN/収集失敗になることを確認。Coordinator側のC系localeでの成功だけでは検出できなかった。
同時にCoordinatorが007指摘に対応する3テストを追加し、走行中のReviewer/Testerが対象の変化を検知して停止した。変更者はCoordinatorであり、他者の変更の削除・復元はしていない。

## 原因

収集コマンドは英語locale固定だが、Ansible module内の再解釈はプロセスlocaleに依存していた。検証工程ではCoordinatorが走行中の差分を編集し、検証対象を固定できていなかった。

## 修正内容

日時解析をlocale非依存の月名対応と数値datetime構築へ変更。C/日本語localeの回帰テストを追加し、再レビュー・再テストでは差分を固定する。本番のscrub、cron、Notion、Slackへは変更・送信していない。

## 確認方法

根拠は案件007/009と006の対応記録。2026-09-11の010独立再レビューはApprove、011独立再テストは日本語/C.UTF-8双方で15件PASS。検証中の差分を固定して再検証を完了した。015監査でも15件PASSを独立確認済み。
