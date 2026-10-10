# agmsg: 起動直後のセッションにseatが張られず、通知が届かない

日付: 2026-10-10
起点: DEVREQ `req-20261010T083745+0900-1337afc8679b0a00`(Operator)
調査依頼と回答: OPREQ `req-20261010T154400+0900-6a9a1a030610846a` / OPRES `req-20261010T181739+0900-ed79b1237c89fd0e`

## 確認した事実

| 事実 | 確認した手段 |
|---|---|
| SessionStart hook(codex)は、seatの記録が無い役を配送対象から外し、bridgeを立てない | ansyのagmsg v1.3.1 `scripts/drivers/types/codex/_session-start.sh` |
| `codex-record-session.sh` はapp-serverの所在を `AGMSG_CODEX_SEAT_KEY` でしか引けない。通常シェルからではloadedスレッドを問えず、直近40件のrolloutから推定し、threadが1つに絞れなければ何も記録せずに終わる | 同 `codex-record-session.sh`、`_app-server.sh` |
| quoryの `new-session.sh` は通常シェルから `codex-record-session.sh` を最大30回呼び、出力を捨ててseatファイルの有無だけを見る | OPRES(Operatorが全文を確認) |
| quoryのOperatorのprojectは、直近40件のrolloutにthreadが19種類ある | OPRES |
| quoryのdelivery statusは、operatorにsession recordもapp-serverも無いと報告する | OPRES |
| ansyのpane 0のClaude Codeでは、SessionStart hookが `homelab/coordinator` と `homelab-ops/coordinator` を席2つと数え、受信の監視を始めずに止まる | ansyの `scripts/session-start.sh` 末尾の分岐と、本日のこのセッション起動時の出力 |
| `spawn.sh` は、起動したエージェントの最初の入力に `actas <name>` を渡して席を張らせる | ansyの `scripts/spawn.sh`、`drivers/types/codex/template.md` |

## 未確認

- quoryの run 配下の記録とbridge・app-serverのログ(Operatorの規範で直接読めない)。直接原因が上の推定失敗であることの最終確認は、修正後の再起動で行う。
- 既読を付けた処理と `read_at`。
- seat key 付きの request を書いたあと、bridge launcher が実際に bridge を立てるか(launcherがrequestを読み直すことはコードで確認、立つことは修正後の起動で確かめる)。
- 起動プロンプトの `inbox.sh` が quory で「No new messages」を返した理由。ansyで同じ read-only sandbox の中から実行すると `unable to open database file`(rc=14)で失敗し、未読は未読のまま残った(使い捨てteamで実測)。quoryの観測とは形が違う。

## 修正

- **quory** `new-session.sh`(repo外。Yoshinobuが適用): `agmsg_bind_seat` は、起動の直前に置いた目印より新しく、`project=` が一致する app-server の seat record から seat key を取り、`AGMSG_CODEX_SEAT_KEY` を付けて `codex-record-session.sh` を呼ぶ。Codex内の `actas` で張る形は採れない(Operatorは `--sandbox read-only` で動き、run配下へ書けない)。bindは attach の後ろでバックグラウンドに回し、結果を `tmux display-message` で pane に出す。失敗表示は消えるまで残す。
- **ansy** `new-session.sh`(repo外): `exec claude "/agmsg actas coordinator"`。
- `docs/ai/context/operations/agent-messaging.md` §10: 張り直しに seat key を渡すことと、その理由を足した。あわせて、claude-code型の登録を `coordinator` だけにすれば受信が自動で始まるという記述を直した。

## 検証

1. ansy(未実施): 別端末から `./new-session.sh --reset`。pane 0で `actas coordinator` が走り、受信の監視が始まること。
2. quory: 修正を適用して完全再起動。coordinatorからのテスト通知が、手動のhistory確認なしでOperatorセッションへ届くこと。**成立(2026-10-10 18:53送信)** — Operatorの画面に「agmsg delivered the following unread messages for homelab-ops/operator」として本文が自動で入った(Yoshinobuが画面を転記)。`delivery.sh status` の出力は見ていない。
3. quory(未実施): seatが張れない状態で、paneに失敗が表示され、通知が未読のまま残ること。
