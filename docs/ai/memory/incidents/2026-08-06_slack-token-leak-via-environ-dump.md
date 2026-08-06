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

**この出力要求に診断上の目的が無かった。**

表向きの理由は消去法だった — wrapper を素で / サービスの mount namespace の中で / User・EnvironmentFile・ハードニング一式を与えた `systemd-run` の使い捨てユニットで、いずれも再現が成功したので「残るは実プロセスの環境だけ」と考えた。しかし成立しない。

- **環境変数は、絶対パスの `execve` が ENOENT を返す原因にならない。** 唯一の経路は `#!/usr/bin/env node` の PATH 解決である
- **その PATH は既に取得済みだった。** 前段で `sudo -H -u recovery-exec env | grep -i '^PATH'` を実行してもらい、`/usr/bin` が入っていることを確認していた

つまり **「何が出たらどう結論するか」を言えない状態で全部出させた。** 仮説が尽きたにもかかわらず「尽きた」と言わず、手順表の (c) という体裁を作って続けたことが直接の引き金である。**目的が言えない出力要求だったため、何を除外すべきかも考えられなかった。**

`roles/recovery_io/templates/recovery-io.env.j2` は先頭2行がトークンであり、確認は grep 一発で済んだ。環境変数へ資格情報を置く設計そのものは不当ではない(`EnvironmentFile` は `0600`)。**壊れたのは読み出し方の側である。**

### 構造的な背景

**dispatch の列挙されたチェックで足りなくなるたび、Coordinator は「このコマンドを打ってください」へ逃げていた。** 同日に4回起きている。

| 足りなかったもの | 代わりにやったこと |
|---|---|
| `journal-unit` が `-n 300` 固定で raw output に届かない | `journalctl` を人に打たせた |
| プロセス一覧を見る手段が無い | 二重リスナーを quory 側では発見できなかった |
| 配備物の中身を読む手段が無い(`codex-exec-wrapper` は `deployed-hash` に無い) | `sed` を人に打たせた |
| 環境変数を見る手段が無い | **`/proc/<PID>/environ` の全出力を人に打たせた ← 本件** |

**照会は forced command の枚挙で閉じているのに、そこから溢れたときの経路は無制限である。** 設計上いちばん危ない操作が、いちばん保護の無い経路へ押し出される。`docs/ai/core.md` の「安全機構がブロックしたら迂回するな」は**「カタログに無いだけ」には掛からない**ため、この経路を止める規定は存在しない。

**手順・規範で縛る対処は採らない**(Yoshinobu、2026-08-06)。`docs/ai/memory/lessons/permission-boundaries-must-be-designed-not-prompted.md` が扱う型そのものであり、Phase 4 で ansy から鍵を抜いたのは手順で守れないからであった。牽制は Operator 役の要件として起こした(`docs/ai/reviews/operator_role/2026-08-05_001_design_notes.md` D9 / OQ4)。

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

### 失効の影響範囲は repo の外へ広く及んだ

旧アプリ削除で止まったのは `common_slack` の通知だけではない。**Proxmox / UniFi Application / UniFi Protect / Grafana の通知設定も、この Slack アプリを指していた**(Yoshinobu、2026-08-06)。いずれも repo 外の機器・アプリ側の設定であり、**張り直しはすべて手作業**である。Semaphore の environment(`slack_webhook_*`)を含めて5系統以上になる。

**Coordinator はこの範囲を測らずに「巻き添えが大きいから回さない」と推奨していた。** 大きさを知らないまま大きいと言い、その未測定の根拠で資格情報を残す側へ倒した。

### ローテーションが露出を広げた

**新しい資格情報は、開発機である ansy へ平文で着地した**(`/etc/recovery-io/` mtime 13:17:35)。さらにそこで recovery-io が起動し(13:17:37)、13:43 の本番イベントを処理した。原因と経緯は `2026-08-06_production-runtime-deployed-to-dev-host.md`。ansy 上の当該ファイルは同日に撤去済み。

**流出への対応が、流出の範囲を広げた。** 配備を指示する前に playbook の `hosts:` を読んでいれば起きなかった。

### 移行にあたって通知と復旧のアプリを分離した

**旧アプリは通知(Incoming Webhook)・復旧(Socket Mode)・App action を1つに載せていた。これがローテーションの天秤を作っていた** — トークンを1本回そうとすると通知経路が全系統倒れる構造である。

**移行時に分離済み**(Yoshinobu、2026-08-06)。Socket Mode は `homelab-recovery` として独立しており、**以後は復旧系のトークンを通知を巻き込まずに回せる。** 上の「失効の影響範囲」は旧アプリ構成での話であり、次回には当てはまらない。

再発防止(手順側):

- **サービスの環境変数を読むときは資格情報を除外して出す。** 丸ごと出す必要はほとんど無い。読む前に、その unit の `EnvironmentFile` がどのテンプレートから来ているかを見る

この対応の過程で判明した、配備側の落とし穴2件:

- **Semaphore はジョブごとに repo を clone するため、commit・push されていない vault は届かない。** 未 push のまま `Recovery io setup` を押すと差分が出ず、**success で終わり handler も発火しない**。実際に task 593 がそうなり、「配備したのに変わっていない」が緑で通った
- **`deployment_drift_check` が recovery-io について見ているのは service の `enabled` / `active` だけ**(`roles/deployment_drift_check/defaults/main.yml`)で、`recovery-io.env` の中身は検査対象外である。quory 側だけを直しても検出されない

## 確認方法

- `ssh quory-investigate "journal-unit recovery-io.service 30m"` で `invalid_auth` が止まり、`A new session has been established` と `Bolt app is running!` を確認(2026-08-06 11:57、PID が 28734 → 457150 へ)
- Slack から @mention し、Codex の応答が返ることを確認
