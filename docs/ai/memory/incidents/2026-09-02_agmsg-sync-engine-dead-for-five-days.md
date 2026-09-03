# Incident: agmsg の sync engine が5日間死んでおり、開発↔運用の連絡が片方向とも出ていなかった

日付: 2026-09-02
状態: 解決済み
対象: agmsg remote team `homelab-ops` の sync engine(ansy側、`~/.agents/skills/agmsg/`、リポジトリ外)
種別: 動作不具合
原因分類: #運用考慮ミス

## 症状

**2026-08-29 09:04 JST から 2026-09-02 17:30 JST までの5日間、ansy から agmsg のメッセージが1通もサーバへ出ていなかった。** 受信も同様に止まっていた。

- `remote.sh status homelab-ops` は `engine stale — pidfile 1274424 points at a dead or foreign process` を返し、PID 1274424 は存在しなかった
- engine ログの最終書き込みは 2026-08-29 09:04、`cycles.json` の `last_success_at` は同 09:04:05
- **ansy の再起動が原因ではない**(boot は 2026-08-17)

**症状は「何も起きないこと」だった。** `send.sh` は成功を返し続け、メッセージはローカルstoreへ入り、履歴にも残る。**出ていないことを示すものが、明示的に見に行かない限りどこにも現れない。**

## 原因

engine が起動時に `teams/homelab-ops/.config.lock` の registry lock を10秒待って取得できず、`roster sync prepare failed` で **fatal 終了**していた。lock は空ディレクトリで、保持プロセスは存在しなかった(stale lock)。

```
agmsg: timed out acquiring registry lock for .../teams/homelab-ops after 10s
agmsg: last mkdir error: mkdir: .../teams/homelab-ops/.config.lock: File exists
```

**lock がどう取り残されたかは未確認。** 作成時刻(08-29 09:04)は engine の最後の成功サイクルと同じ分であり、engine 自身の異常終了で残した可能性が高いが、確かめていない。

## 実害

| 何が止まっていたか | 実際に起きたこと |
|---|---|
| Operator → Coordinator | 2026-09-01 17:55 JST の「OPRES送信完了」通知が**届かなかった**。Coordinator は `status` / `list` を叩いて初めて回答済みと気づいた |
| Coordinator → Operator | 2026-09-01 と 2026-09-02 のOPREQ通知2通が**出ていなかった** |

**2026-09-01にOperatorが調査へ着手できたのは、Yoshinobuが直接伝えたからである**(本人談、2026-09-02)。agmsgの通知は届いておらず、**人が経路の外で埋めていた**。埋められたために、経路が死んでいること自体が誰にも見えなかった。

**OPREQ本体は影響を受けていない。** spoolへの登録は SSH の forced command 経由で、agmsg とは別経路である。届いていなかったのは通知だけである。

## この Incident が変えた見立て

**2026-09-02 の案件 `agmsg_notification_pairing` は、「OPRESが返っても誰も知らせてくれない」を規範の欠落として起案した。それは誤りだった** — Operator は9/1に通知を送っており、**運んでいた транспорт が死んでいた**。同案件の是正(登録と通知を1操作にする)自体は有効だが、9/1に観測された症状の原因ではない。

**同案件が入れた `scripts/oprc-submit.sh` は、この穴をそのまま通った。** team と identity は事前に検査していたが、**通知がホストから出られる状態かを見ていなかった**。同日中に engine の生死と直近の同期成功を submit 前の検査へ加えた。

## 発見の経緯(この経緯自体が知見)

**Yoshinobu の「agmsg本当に送ってる?」という問いで見つかった。** Coordinator は `send.sh` の終了コードと `登録: / 通知:` の2行をもって「送信済み」と報告しており、**それが意味するのはローカルstoreへの書き込みまでだった**。

`docs/ai/context/operations/agent-messaging.md` §9 は既に「`engine running` の1行だけで判断しない。見るのは**最後に成功した同期**の行である」と書いていた。**書かれていたのに、実装にも報告にも落ちていなかった。**

## 対処

1. stale lock(空ディレクトリ、保持プロセスなし)を除去した
2. **Yoshinobu が通常のシェルから** `remote.sh sync start homelab-ops` を実行した(§9: エージェントのツール実行から起動するとプロセスグループごと刈られ、ログにも残らない)
3. 溜まっていた3通が両方向へ流れた
4. `scripts/oprc-submit.sh` に submit 前の同期検査を追加した(engine 稼働 + 直近30分以内の同期成功。いずれも満たさなければ登録しない)

## 残っている弱点

- **engine の死を能動的に知る仕組みは無い。** 今回も5日気づかなかった。次に死ねば同じだけ黙る
- **engine は systemd unit ではなく、リブートで必ず落ちる。** 戻すのはセッション開始時の自動起動だけである(§9)
- 対処4が守るのは **OPREQの経路だけ**である。`send.sh` を直接使う経路(codex Reviewer への依頼は local team なので影響しないが、`homelab-ops` への手動送信)は同じ穴を通る
