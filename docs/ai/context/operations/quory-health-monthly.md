# quory月次ヘルスレポート

状態: 実quoryでnative `--check`の収集成功を確認済み・初回公開前。案件正本は `docs/ai/reviews/quory_health_monthly/2026-09-13_001_requirement.md`、計画は002、方式選択はADR-014、業務規範は `docs/ai/policies/quory_health_monthly_policy.md`。

## 入口

`playbooks/quory_health_monthly.yml`。観測対象は`control_nodes`グループの`quory`単体で、他ホストへは触れない。NVMe取得ツールが実行コンテキストに無ければ観測は導入せず取得不能として報告する。Yoshinobuがquoryへ手動で`nvme-cli`を導入し、Semaphore #1093のnative `--check`で収集成功・判定OKを確認した（詳細は下の「NVMe取得ツールの手動導入」節）。
許可・禁止・停止条件の正本は `docs/ai/policies/quory_health_monthly_policy.md`。本書は実行方法、保存形式、配備状態を記録するOperations Contextであり、実行境界を上書きしない。

変数の既定値は `roles/quory_health_monthly/defaults/main.yml`。操作は `quory_health_monthly_operation=collect` または `replay`。再送は `quory_health_monthly_report_id` に保存済report IDを指定する（ファイルパスは受け付けない）。replayでは対象hostへ収集しない。

## 保存と読み方

`quory_health_monthly_report_dir`（既定 `{{ reports_base_dir }}/quory-health-monthly`）にreport IDごとのJSONとMarkdownを保存する。JSONが観測正本、Markdownが人向け正式本文、Notionは同月1ページの参照コピー。収集・公開に失敗しても既存レポートを消さない。
`<month>.baseline.json` は月の比較基準。デバイスごとに前月以前の直近成功値を固定し、過去値が無ければ当月最初の成功値を固定する。同月再実行で差分は消えない。deviceの`comparison_source`に比較元のIDと日時を記録する。
`<month>.publication.json` は公開処理の状態、report IDごとのpublished JSONは公開完了の記録。13か月より古い公開済履歴だけが整理対象となり、比較基準の参照先・未公開・破損は保全するため、実保持期間は13か月を超える場合がある。保存形式・原子性・保持ロジックは`proxmox_storage_monthly`と同じ契約だが、独立した実装・独立したテストである（ADR-014）。

healthと処理結果は別軸である。ファイルシステム/メモリ/NVMeのWARNING・CRITICALがあっても収集・保存・公開が完了すればジョブはrc0。**ただしNVMe/SMART指標や必須値が取得・解釈できずhealth=UNKNOWNになった場合は、収集・保存・公開自体が完走していてもジョブをrc非0にする**（QHM-031、requirement AC2）。この判定は`roles/quory_health_monthly/tasks/report.yml`最終assertが`health != 'UNKNOWN'`を明示的に見て行う — `proxmox_storage_monthly`はNVMeコマンド失敗を`collection: error`に畳んでいたが、本roleはfilesystem/memoryが収集できていればNVMe取得不能だけでcollectionをerrorにせず、health軸で失敗を表す（容量が正常でも「ディスク健全」と誤読ませないための分離）。
Slackは既存common_slackのbest-effort通知。ジョブrc0だけからSlack到達を判断しない。

## Notionの配備前提

Yoshinobuが「quory 月次ヘルス」ページを作成し、Notion上でページID `3da22f45-f1b0-802b-b069-e4d6da7c3311` と `homelab運用` 配下であることを確認した。`quory_health_monthly_notion_parent`の既定値はこの専用ページとする。既存の`homelab-report` IntegrationとProxmoxストレージ月次点検が使うquory上の権限制限付きtokenファイル（既定 `/etc/homelab/notion-storage.token`）を再利用し、新しいtokenは作らない。Yoshinobuは新ページの「接続」に`homelab-report`が表示されることを確認した。API側の実効権限と投稿結果は初回公開時のreadbackで確認する。tokenをチャット、Git、extra-vars、コマンド引数に貼らない。
投稿APIはapi.notion.com固定、TLS検証有効。作成の応答消失時にはcreating予約を残し、再送で親ページ配下のtitle+管理markerを照合する。一意に確認できなければ停止する。

## 検証と抑止

native `--check` は観測・判定のみで、保存・token読取・Notion・Slack・host変更を行わない。`skip_notifications=true` は通常実行でもNotionとSlackを止める（ローカル保存は行う）。Notion専用forceはAI環境検出だけを解除し、check/skipは解除できない。
ローカルfixture: `python3 -m unittest discover -s tests -p test_quory_health_monthly.py -v`。

## NVMe取得ツールの手動導入

Semaphore #1083のnative `--check`が`/dev/nvme0n1`を`tool_unavailable`・rc=2で記録し、OPRES `req-20260913T103425+0900-66100285a5cf808c`も`nvme-cli`不在を確認した。当初は専用setup playbook/roleを作成したが、template setupのDry Run #1092で新規setupテンプレート1件に加えて既存の別テンプレート2件のSurvey metadata差分が見つかったため適用を見送った。

Yoshinobuがquoryで`sudo apt update`、`sudo apt install --no-install-recommends nvme-cli`を手動実行し、`sudo nvme version`が2.16を返すことを確認した。#1093の月次観測Dry Runはrc=0・判定OKで、当初の`tool_unavailable`失敗は解消した。この一度きりの導入のために作った専用playbook/role/catalog項目は未配備のまま削除し、月次観測入口にパッケージ導入を混ぜない境界（QHM-011/QHM-020）は維持した。既存2件のSurvey差分は別件として扱う。

## 未確定・今回スコープ外

- quoryの`nvme version`と#1093の収集成功は確認済み。`nvme id-ctrl`/`nvme smart-log`個別の出力値はジョブログからは確認していない。
- Notionページは作成済み。Integration権限の実効readback。
- 月次schedule（Semaphore・quory自身の定期処理との重複照合が未実施のため`roles/semaphore_templates/defaults/main.yml`の`schedules`へは今回追加していない）。NVMe setup用のtemplate/scheduleも登録していない。

## 経過観察

初期実装と独立差分レビュー（009 Approve）は完了。Testerのfixture/unit 53件とsyntaxはPASS（011）。ただし実host名入りinventoryと非check実行は境界違反として検証根拠から外し、当時のfull-playbook結合はNot Run、AC5はPartialと訂正した。その後、Semaphore #1083はツール不在を検出し、手動導入後の#1093は実quoryでのnative `--check`収集に成功した。正式レポートの保存・Notion投稿・Slack通知とscheduleの配備readbackは未着手。
