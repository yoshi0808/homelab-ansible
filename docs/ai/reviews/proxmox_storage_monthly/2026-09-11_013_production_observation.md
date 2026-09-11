# 初回本番観測とスケジュール有効化準備

状態: 初回実行・schedule有効化確認済み。案件全体のcloseoutは014を参照。

## 証拠

- #1052: templates setupはDry Runではなくapplyで成功。新規template ID 59、schedule ID 24。既存template55件/schedule22件は無変更。schedule作成後のround-trip検証成功。Coordinatorがforced commandでtask-time/outputと両latest.jsonを確認。
- OPRES `req-20260911T173047+0900-e38dbc8868c0e80c`（対応OPREQ `req-20260911T172201+0900-c1f79eadceefde5d`）をCoordinatorが取得。
- Operatorが#1056の通常collect成功、両pveのcollection=ok、ZFS ONLINE、NVMe3台の値の解析成功を報告。JSON/Markdownのreport IDは `20260911T171734757310+0900-8f379bfbe14e4ef89826a59c93594764`。health=OK、history_error=false、issuesなし。
- pve2のerror-log累積239は初回baseline。差分比較はまだ発生していない。原因や故障とは断定しない。
- OperatorがNotion API GETで月次ページのparent、管理marker、公開完了行とreport IDの一致を確認。publication=published、receipt一致。
- Yoshinobuが会話でSlack通知とNotionリンクの到達を確認した。

## 有効化

初回観測後、Yoshinobuが毎月15日08:00の有効化を承認。catalogを変更し、`f87f4e9`をcommit/pushした。Yoshinobuが#1058を通常実行し、2026-09-11 17:41:36〜17:42:04 JSTに成功した。

Coordinatorがforced commandの`semaphore-query task-time 1058`、`task-output 1058`、`report-show semaphore-templates latest.json`、`report-show semaphore-schedules latest.json`で確認。両reportの生成日時は同ジョブ時間内。schedule ID24/template ID59の変更はactive=false→trueのみ、cronは`0 8 15 * *`、timezoneはAsia/Tokyo。書込後のVerify成功、非管理field変更のguardは発火せず。他schedule22件は無変更。

予想したschedule1件だけでなく、template ID59の任意Replay report ID欄へ`required=false`と`default_value=""`を補う差分も報告された。新規templateはなく、他55件は無変更。この差分は明記してYoshinobuへ報告済み。APIが空値を省略することによる反復差分かどうかは未確認であり、冪等性確認済みとは扱わない。

## 残り

案件closeout/Auditor。次回定期実行による前回比較は経過観察。Luna省トークンのベンチマークは最終利用枠が未提示のため定量評価未了。
