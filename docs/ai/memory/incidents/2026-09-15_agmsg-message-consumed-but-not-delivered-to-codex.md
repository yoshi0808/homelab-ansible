# Incident: agmsgのメッセージが既読になるのに、Codexの可視スレッドへ届かない

日付: 2026-09-15
状態: 未解決(原因未特定。回避策は確立しており、実害は遅延のみ。次のセッションで調査する)
対象: agmsgのcodex monitor経路(ansy pane 1 Implementer / pane 2 計画Reviewer)
種別: 動作不具合

## 症状

CoordinatorがCodexの役へ `send.sh` で依頼を送ると、**メッセージはDBに入り、`history.sh` にも現れるのに、Codexのペインが一切反応しない。** 2026-09-15に**5回**発生した(Implementerへ3回、Reviewerへ2回)。**5回ともYoshinobuが先に気づいた** — Coordinatorが送りっぱなしにしていたためである。

**5回とも、相手が直前の応答を終えた直後の送信だった。** ただし同じ条件で成功した送信も多数あり、必要条件でも十分条件でもない。

**用語の注意**: 以下で使う「応答1回」は、bridgeのログが `started turn` / `turn completed` と書いているもの、つまり**Codexスレッドが1回答える単位**である。**`delivery.sh` の配送モードの `turn` とは無関係**であり、この環境の配送モードは一貫して `monitor` である(`docs/ai/context/operations/agent-messaging.md` §2。`turn` モードは2026-09-08に実測して不採用)。

観測される状態は毎回同じである。

| 観測 | 値 |
|---|---|
| `watch-once.sh --name <役>` | **exit=2(未読なし)** — 誰かが既に既読にしている |
| `delivery.sh status codex <project>` | `alive (pid ...)` |
| bridgeのログ | **`wakeup N` が増えない**(その送信に対応する取り込みが起きていない) |
| ペイン | 直前の応答の表示のまま、無反応 |

**`started turn` / `turn completed` は判定に使えない。** 前の応答の行がログに残るため、新しいメッセージが届いていなくても「動いた」ように読める。**Coordinatorは実際にこれで一度誤判定した。** 取り込みの証拠は **`wakeup N` の番号が増えること**だけである。

## 原因

未判明。**測っていない候補が1つある** — Coordinator自身の `watch.sh`(Monitor tool経由で常駐)には、**自分宛でないメッセージ(`coordinator → implementer` など)もイベントとして流れてくる**。同じメッセージをCodexのbridgeと取り合い、先に既読へ倒している可能性がある。ただし**どちらが先に既読にしたかは測っていない**ため、断定しない。

同日の別Incident(`2026-09-15_...` ではなく `2026-09-14_agmsg-codex-bridge-not-armed-after-reboot.md`)は「bridgeがそもそも起動していない」ケースで、**これとは別の壊れ方である**(今回はbridgeが生きている)。

## 修正内容

未実施。**回避策は確立している** — 該当ペインへ `tmux send-keys` で「`history.sh` を読んで最新の依頼を実行せよ」と入れると、5回とも復旧した。依頼本文はDBに入っているため、この方法は「依頼をDBに通す」という規律(`docs/ai/context/operations/agent-messaging.md` §6)を壊さない。

## 確認方法

原因特定後に定める。次に再発したときに測るべきものは決まっている。

- **既読にした主体はどちらか** — Coordinatorの `watch.sh` を止めた状態で同じ送信を行い、bridgeが `wakeup` するかを見る
- agmsgのDB(SQLite)の既読カーソルが、どのsubscriptionによって進んだか

## 当面の運用(2026-09-15から)

**送信のたびに `wakeup N` が増えたかを確認し、増えていなければその場でペインへ読ませる。** 送信して終わりにしない。
