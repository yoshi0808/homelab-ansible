# Incident: 調査手順で Slack トークンを流出させた

日付: 2026-08-06
状態: 調査中(bot トークンのローテーションが未実施)
対象: roles/recovery_io / Coordinator の調査手順
種別: セキュリティ事故
原因分類: #運用考慮ミス

## 症状

`2026-08-06_codex-exec-wrapper-intermittent-enoent.md` の調査中、Coordinator が `/proc/<MainPID>/environ` を丸ごと出力する手順を提示した。`recovery-io.service` の `EnvironmentFile` には Slack のトークンが入っており、**実値が端末のスクロールバックと対話ログへ出た。**

出たもの:

| 値 | 扱い |
|---|---|
| `SLACK_BOT_TOKEN`(xoxb-) | ローテーション対象 |
| `SLACK_APP_TOKEN`(xapp-) | ローテーション対象 |
| `RECOVERY_AUTHORIZED_USER_ID` | Slack のユーザーIDであり認証能力を持たない。対象外 |

実害の評価:

- **bot トークンだけでは復旧コマンドを実行できない。** `handle_mention` はイベント送信者の user ID が `RECOVERY_AUTHORIZED_USER_ID` と一致するかを見ており、bot として発言しても一致しない
- **app トークンのほうが実害が大きい。** Socket Mode へ接続すると @mention のイベントを受け取れ、正規のリスナーからイベントを奪える

## 原因

調査手順の設計。**環境変数を丸ごと出力させる前に、そこへ資格情報が入る設計かどうかを確認しなかった。** `roles/recovery_io/templates/recovery-io.env.j2` は先頭2行がトークンであり、確認は grep 一発で済んだ。

環境変数へ資格情報を置く設計そのものは変えていない。`EnvironmentFile` は `0600` で置かれており、設計として不当ではない。**壊れたのは読み出し方の側である。**

## 修正内容

**旧アプリをワークスペースから削除し、新アプリ `homelab-recovery` へ移行した(Yoshinobu、2026-08-06)。流出した両トークンは失効済みである。**

- 旧アプリの削除により、bot トークン・app トークン・**Incoming Webhook URL** がすべて同時に失効した
- Socket Mode の新トークンを `inventories/vars/slack.yml`(ansible-vault)へ入れ、commit `eda2d54` で push、Semaphore の `SEMI-SAFE: Recovery io setup` で配備
- **通知用の webhook URL は repo でなく Semaphore の environment にあるため、Yoshinobu が手作業で差し替えた**
- 新アプリでは Event Subscriptions の `app_mention` 購読とチャンネルへの招待が別途必要だった(新規アプリでは既定で付かない)

### 経緯として残すこと: 一時は「回さない」と判断しかけた

Slack の仕様上、scope 無変更の再インストールでは bot トークンは**同じ文字列が再発行される**。実際に変えるには `auth.revoke` かアプリ削除が要る。ところが **Incoming Webhook URL と App action が同じアプリに載っていた**ため、どちらも通知経路を巻き込む。しかも webhook URL は repo に無く Semaphore の environment にしかないので、張り直しは手作業でAIから検証もできない。

そこでCoordinatorは「bot トークン単体では復旧コマンドを実行できない(送信者の user ID で弾かれる)」ことを根拠に**リスク受容を推奨した**。Yoshinobu はこれを退けた(「放置できないでしょ」)。

**判断としてはYoshinobuが正しかった。** 実際にやってみると、旧アプリ削除 → 新アプリ作成 → 移行は同日中に完了している。**Coordinator は「巻き添えの大きさ」を理由に、資格情報を失効させないという結論へ寄せた。** 巻き添えは作業手順で吸収できる種類のものであり、資格情報が生きていることと釣り合う天秤ではなかった。

### 残る構造上の問題

**通知(Incoming Webhook)と復旧(Socket Mode)が、いまも同一の Slack アプリに載っている。** 今回はアプリを丸ごと作り直したので通ったが、**次にトークンを1本回そうとすると同じ天秤にまた乗る。** 分離すれば、復旧系のトークンは通知を巻き込まずに回せる。`docs/ai/status.md` の Next に起こした。

再発防止(手順側):

- **サービスの環境変数を読むときは資格情報を除外して出す。** 丸ごと出す必要はほとんど無い。読む前に、その unit の `EnvironmentFile` がどのテンプレートから来ているかを見る

この対応の過程で判明した、配備側の落とし穴2件:

- **Semaphore はジョブごとに repo を clone するため、commit・push されていない vault は届かない。** 未 push のまま `Recovery io setup` を押すと差分が出ず、**success で終わり handler も発火しない**。実際に task 593 がそうなり、「配備したのに変わっていない」が緑で通った
- **`deployment_drift_check` が recovery-io について見ているのは service の `enabled` / `active` だけ**(`roles/deployment_drift_check/defaults/main.yml`)で、`recovery-io.env` の中身は検査対象外である。quory 側だけを直しても検出されない

## 確認方法

- `ssh quory-investigate "journal-unit recovery-io.service 30m"` で `invalid_auth` が止まり、`A new session has been established` と `Bolt app is running!` を確認(2026-08-06 11:57、PID が 28734 → 457150 へ)
- Slack から @mention し、Codex の応答が返ることを確認
