# quory月次ヘルスレポート

状態: 初期実装完了・実ホスト未配備。案件正本は `docs/ai/reviews/quory_health_monthly/2026-09-13_001_requirement.md`、計画は002、方式選択はADR-014、業務規範は `docs/ai/policies/quory_health_monthly_policy.md`。

## 入口

`playbooks/quory_health_monthly.yml`。観測対象は`control_nodes`グループの`quory`単体で、他ホストへは触れない。NVMe取得ツールが実行コンテキストに無ければ観測は導入せず取得不能として報告する — 導入は別のquory限定setup入口`playbooks/quory_nvme_setup.yml`に分離している（実装済み・実ホスト配備は未着手。詳細は下の「NVMe取得ツールの配備」節）。
許可・禁止・停止条件の正本は `docs/ai/policies/quory_health_monthly_policy.md`。本書は実行方法、保存形式、配備状態を記録するOperations Contextであり、実行境界を上書きしない。

変数の既定値は `roles/quory_health_monthly/defaults/main.yml`。操作は `quory_health_monthly_operation=collect` または `replay`。再送は `quory_health_monthly_report_id` に保存済report IDを指定する（ファイルパスは受け付けない）。replayでは対象hostへ収集しない。

## 保存と読み方

`quory_health_monthly_report_dir`（既定 `{{ reports_base_dir }}/quory-health-monthly`）にreport IDごとのJSONとMarkdownを保存する。JSONが観測正本、Markdownが人向け正式本文、Notionは同月1ページの参照コピー。収集・公開に失敗しても既存レポートを消さない。
`<month>.baseline.json` は月の比較基準。デバイスごとに前月以前の直近成功値を固定し、過去値が無ければ当月最初の成功値を固定する。同月再実行で差分は消えない。deviceの`comparison_source`に比較元のIDと日時を記録する。
`<month>.publication.json` は公開処理の状態、report IDごとのpublished JSONは公開完了の記録。13か月より古い公開済履歴だけが整理対象となり、比較基準の参照先・未公開・破損は保全するため、実保持期間は13か月を超える場合がある。保存形式・原子性・保持ロジックは`proxmox_storage_monthly`と同じ契約だが、独立した実装・独立したテストである（ADR-014）。

healthと処理結果は別軸である。ファイルシステム/メモリ/NVMeのWARNING・CRITICALがあっても収集・保存・公開が完了すればジョブはrc0。**ただしNVMe/SMART指標や必須値が取得・解釈できずhealth=UNKNOWNになった場合は、収集・保存・公開自体が完走していてもジョブをrc非0にする**（QHM-031、requirement AC2）。この判定は`roles/quory_health_monthly/tasks/report.yml`最終assertが`health != 'UNKNOWN'`を明示的に見て行う — `proxmox_storage_monthly`はNVMeコマンド失敗を`collection: error`に畳んでいたが、本roleはfilesystem/memoryが収集できていればNVMe取得不能だけでcollectionをerrorにせず、health軸で失敗を表す（容量が正常でも「ディスク健全」と誤読ませないための分離）。
Slackは既存common_slackのbest-effort通知。ジョブrc0だけからSlack到達を判断しない。

## Notionの配備前提（未確定）

Notion親ページIDは`quory_health_monthly_notion_parent`が既定空文字列であり、**readbackで確定するまで公開は成立しない**（`quory_health_notion`モジュールが`parent_unconfirmed`で失敗する）。既存の`homelab-report` IntegrationとProxmoxストレージ月次点検が使うquory上の権限制限付きtokenファイル（既定 `/etc/homelab/notion-storage.token`）を再利用し、新しいtokenは作らない。新ページへのIntegration権限は別途readbackする。tokenをチャット、Git、extra-vars、コマンド引数に貼らない。
投稿APIはapi.notion.com固定、TLS検証有効。作成の応答消失時にはcreating予約を残し、再送で親ページ配下のtitle+管理markerを照合する。一意に確認できなければ停止する。

## 検証と抑止

native `--check` は観測・判定のみで、保存・token読取・Notion・Slack・host変更を行わない。`skip_notifications=true` は通常実行でもNotionとSlackを止める（ローカル保存は行う）。Notion専用forceはAI環境検出だけを解除し、check/skipは解除できない。
ローカルfixture: `python3 -m unittest discover -s tests -p test_quory_health_monthly.py -v`。

## NVMe取得ツールの配備（別入口）

Semaphore #1083のnative `--check`が`/dev/nvme0n1`を`tool_unavailable`・rc=2で記録し、OPRES `req-20260913T103425+0900-66100285a5cf808c`も`nvme-cli`不在を確認した。要求追補012・計画追補013に基づき、`playbooks/quory_nvme_setup.yml`（role: `roles/quory_nvme_setup`）を新設した。`quory_health_monthly.yml`本体・`roles/quory_health_monthly/`は変更していない（QHM-011/QHM-020: 観測入口はパッケージ導入をしない）。

package_factsで導入状態を読み、未導入のときだけAPT cacheを更新して`nvme-cli`を導入するrole。native `--check`はapt moduleのcheck_modeでパッケージ変更なしにプレビューし、導入後のCLI実行可否確認（`nvme version`）は`when: not ansible_check_mode` + `tags: [destructive]`のblockに閉じているため`--check`では実行されない。playbookの前後には対象不在・対象0件の空成功を検出するlocalhostのguardがある。Semaphore templateは引数なし・専用1件のみを追加し、scheduleは追加していない（P0で明示的に対象外）。

配備順序（計画013）: commit/push→Yoshinobuがtemplate setupのcheck→apply→readback→専用setupのcheck→apply→readback（`nvme version`の出力で実行可否を確認）→月次ヘルスジョブの`--check`を再実行し`tool_unavailable`が消えたかを確認。取得が続けば権限・デバイス・CLI出力形式を別途調べ、通常のcollect実行には進まない。

## 未確定・今回スコープ外

- quory実ホストでの実際の導入結果・`nvme id-ctrl`/`nvme smart-log`の成功可否（要求012 オープンクエスチョン、実機readback待ち）。
- Notion親ページIDとIntegration権限。
- 月次schedule（Semaphore・quory自身の定期処理との重複照合が未実施のため`roles/semaphore_templates/defaults/main.yml`の`schedules`へは今回追加していない。templateのみ追加済み）。NVMe setup用のscheduleも同様に追加していない（自動導入は今回の対象外）。

## 経過観察

初期実装と独立差分レビュー（009 Approve）は完了。Testerのfixture/unit 53件とsyntaxはPASS（011）。ただし実host名入りinventoryと非check実行は境界違反として検証根拠から外し、full-playbook結合はNot Run、AC5はPartialと訂正した。実ホストreadback、Notion/schedule配備は未着手。
