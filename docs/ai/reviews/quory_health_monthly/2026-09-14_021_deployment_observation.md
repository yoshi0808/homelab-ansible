# quory月次ヘルス 初回配備観測

## 初回通常実行

- Semaphore #1094 `SEMI-SAFE: Quory health monthly` は2026-09-14 07:19 JSTに成功（`semaphore-query task-time 1094`、約27秒）。native `--check`成功は#1093。
- Report ID: `20260914T071937629005+0900-7df788d63bf44a23ae82fbc7d8ad489e`。Yoshinobuがquory上の同IDのJSON・Markdown・published JSONの存在、ownerと0600権限を確認した。
- Notionの[2026-09月次ページ](https://app.notion.com/p/3da22f45f1b08107923cdcd542d9af03)をCoordinatorが再取得し、専用親ページ配下・同ID・対象quory・判定OKを確認した。Slack #infoの[短報](https://homelab-k0t2012.slack.com/archives/C0B4UKNGY2Z/p1789337994289339)も同IDで確認済み。
- 保存・Notion・Slackの照合は成立。これは次回の定期実行や障害時の成功保証ではない。

## schedule

YoshinobuはProxmox月次レポート（毎月15日08:00 JST）の次のジョブを指定した。具体的な時刻は未確定。schedule定義・配備・active/日時のreadbackは未実施。時刻照合のOPREQ 2件（`req-20260914T073123+0900-682eeac7602a7358`、`req-20260914T073236+0900-e0720746d0de4f19`）は提出後に追加調査不要とOperatorへ通知した。Channel上の終状態は未確認。
