# 初回本番観測とスケジュール有効化準備

状態: 初回実行確認済み。有効化カタログは変更済み、本番反映待ち。案件全体のcloseoutではない。

## 証拠

- #1052: templates setupはDry Runではなくapplyで成功。新規template ID 59、schedule ID 24。既存template55件/schedule22件は無変更。schedule作成後のround-trip検証成功。Coordinatorがforced commandでtask-time/outputと両latest.jsonを確認。
- OPRES `req-20260911T173047+0900-e38dbc8868c0e80c`（対応OPREQ `req-20260911T172201+0900-c1f79eadceefde5d`）をCoordinatorが取得。
- Operatorが#1056の通常collect成功、両pveのcollection=ok、ZFS ONLINE、NVMe3台の値の解析成功を報告。JSON/Markdownのreport IDは `20260911T171734757310+0900-8f379bfbe14e4ef89826a59c93594764`。health=OK、history_error=false、issuesなし。
- pve2のerror-log累積239は初回baseline。差分比較はまだ発生していない。原因や故障とは断定しない。
- OperatorがNotion API GETで月次ページのparent、管理marker、公開完了行とreport IDの一致を確認。publication=published、receipt一致。
- Yoshinobuが会話でSlack通知とNotionリンクの到達を確認した。

## 有効化

初回観測後、Yoshinobuが毎月15日08:00の有効化を承認。catalogの当該scheduleだけactive=trueへ変更する。Git確定とSemaphore templates setupのapply、schedule readbackはこれからであり、現時点で本番のactive=trueを確認したとは扱わない。

## 残り

schedule有効化readback、案件closeout/Auditor。次回定期実行による前回比較は経過観察。Luna省トークンのベンチマークは最終利用枠が未提示のため定量評価未了。
