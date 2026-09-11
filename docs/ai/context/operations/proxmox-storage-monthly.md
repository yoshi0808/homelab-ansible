# Proxmoxストレージ月次点検

状態: 独立ローカル検証完了・本番未配備。案件正本は `docs/ai/reviews/proxmox_storage_monthly/2026-09-10_001_requirement.md`。

## 入口

`playbooks/proxmox_storage_monthly.yml`。既存cronのscrubは変更しない。収集はZFS状態と実vdevのNVMe healthのみで、self-test・修復を開始しない。
実行はquoryのSemaphoreから。2026-09-10にユーザー提示の工程管理表と照合し、掲載された処理と開始時刻が重ならない毎月15日08:00 JSTをcatalogへ登録した。長時間ジョブの終了時刻までは表から確認できない。scheduleは初回readback完了までactive=false。本番reconcile・有効化は未実施。

変数の既定値とNotion親ページは `roles/proxmox_storage_monthly/defaults/main.yml`。操作は `proxmox_storage_monthly_operation=collect` または `replay`。再送は `proxmox_storage_monthly_report_id` に保存済report IDを指定する（ファイルパスは受け付けない）。replayでは対象hostへ収集しない。

## 保存と読み方

`proxmox_storage_monthly_report_dir` にreport IDごとのJSONとMarkdownを保存する。JSONが観測正本、Markdownが人向け正式本文、Notionは同月1ページの参照コピー。収集・公開に失敗しても既存レポートを消さない。
`<month>.baseline.json` は月の比較基準。デバイスごとに前月以前の直近成功値を固定し、過去値が無ければ当月最初の成功値を固定する。同月再実行で差分は消えない。deviceのcomparison_sourceに比較元のIDと日時を記録する。
`<month>.publication.json` は公開処理の状態、report IDごとのpublished JSONは公開完了の記録。13か月より古い公開済履歴だけが整理対象となり、比較基準の参照先・未公開・破損は保全するため、実保持期間は13か月を超える場合がある。

healthと処理結果は別である。ZFS/NVMe異常があっても収集と公開が完了すればジョブrc0、未確認・保存失敗・Notion失敗はrc非0。初回error-log累積239は故障宣言ではなく比較基準。増加は要確認、減少はreset疑いとして表示する。
Slackは既存common_slackのbest-effort通知。ジョブrc0だけからSlack到達を判断しない。

## Notionの配備前提

内部Integrationへ対象ページの読取・挿入・更新権限を与える。tokenはquoryに専用0600の通常ファイルとして管理者が配置する。既定の配置先はrole defaults参照。tokenをチャット、Git、extra-vars、コマンド引数に貼らない。
投稿APIはapi.notion.com固定、TLS検証有効。Notionの接続ツールでページが読めることと、quoryのIntegrationが投稿できることは別である。

作成の応答消失時にはcreating予約を残し、再送で親ページ配下のtitle+管理markerを照合する。一意に確認できなければ停止する。確認なしでstateを削除して再実行しない。人がNotion本文を追記する場合は管理本文の末尾へ追加し、先頭の管理blockを移動・削除しない。
古いreportの再送による新しい同月ページの巻戻しは拒否する。最新の保存済report IDで再送する。

## 検証と抑止

native `--check` は観測・判定のみで、保存・Notion通信を行わない。`skip_notifications=true` は通常実行でもNotionとSlackを止める（ローカル保存は行う）。Notion専用forceはAI環境検出だけを解除し、check/skipは解除できない。`slack_force_send` はNotionに作用しない。
本番以外の検証ではskip_notificationsを明示する。CodexではCLAUDECODE環境変数が無い場合があり、自動検出だけに依存しない。
ローカルfixture: `python3 -m unittest discover -s tests -p test_storage_monthly.py -v`。

## 未完了

独立差分レビュー010=Approve、Tester再検証011=PASS。Integration準備、実pve出力一致確認、quory初回実行とJSON/Notion/Slack/schedule readbackは未完了。配備済みとは扱わない。
