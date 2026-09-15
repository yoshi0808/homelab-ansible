# Incident: agmsgのメッセージが既読になるのに、Codexの可視スレッドへ届かない

日付: 2026-09-15
状態: **原因特定(2026-09-15)。Coordinator側を`actas`モードにして再発を止めたが、これはセッションごとに取り直す運用であり、恒久対処(roster登録の整理)は未実施**
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

**Coordinator(Claude Code)自身の `watch.sh` が、Codexの役宛のメッセージを先に既読にしていた。** 3つの事実の積である。

1. **roster上、Codexの役のペアはclaude-codeにも登録されている。** `~/.agents/skills/agmsg/teams/<team>/config.json` の `$.agents.<name>.registrations` で、`homelab/implementer` と `homelab/reviewer` が `claude-code` と `codex` の両方を持つ。`identities.sh <project> claude-code` はこのprojectで**17ペア**を返す(ADR-013期の実験名を含む)。
2. **`actas` の排他ロックが1つも存在しなかった。** active nameを指定せずに起動した `watch.sh` は、**誰も確保していない全ペアを購読する**(`scripts/lib/subscription.sh`)。`run/actas.*.session` は空で、「常駐Codexは `actas implementer` 排他」という理解は現物と食い違っていた。
3. **既読カーソルは (team, agent) に1つしかない**(`messages.read_at` と `read_cursors`)。同じペアを2つの購読者が読むと、**先に取った側が行を持ち去り、もう一方は「未読なし」と正しく答える。** `watch.sh` 自身のコメントがこの危険を明示している。

**Codexのbridgeは、turnを回している間そのペアの購読を外す**(ログの `turn completed` → `armed` の間隔)。Coordinatorのwatcherにはその中断が無いため、**この窓に着いたメッセージはwatcher側が取る。** 「直前の応答を終えた直後の送信で起きた」という5回の記録はこの窓と一致する。**bridgeがarmされている間はbridgeが勝つこともある**(下表のA)。

## 確認方法(2026-09-15に実施)

**3秒差の連投**という同じ形で、Coordinatorのwatcherの状態だけを変えて測った。`wakeup` はbridge pid 704307のもの。

| watcherの状態 | 送信 | `wakeup` 増分 | 応答 | 取った側 |
|---|---|---|---|---|
| unfiltered | A(単発) | +1 | `ack A` | bridge |
| unfiltered | B → 3秒 → C | **+1(Bのみ)** | **`ack B` のみ** | **CはCoordinatorのwatcher** |
| 停止 | D → 3秒 → E | +2 | `ack D` `ack E` | bridge |
| `actas coordinator` | F → 3秒 → G | +2 | `ack F` `ack G` | bridge |

**Cが消えた瞬間の直接の証拠は、Coordinator自身の受信イベント列に `coordinator → implementer` の本文が現れたことである。** 宛先が自分でないメッセージを自分が受け取っており、同時にbridgeの `wakeup` は増えていない。

## 修正内容

**Coordinatorのwatcherを `actas coordinator` で起動する形へ変えた**(`actas-claim.sh <project> claude-code coordinator <session_id>` → `watch.sh <session_id> <project> claude-code coordinator`)。購読は `homelab-ops/coordinator` と `homelab/coordinator` の2ペアに限られ、Codexの役のペアに触れなくなる。上表Fの列が成立を示す。

**これはセッションごとに取り直しが要る。** SessionStartのhookが渡す `watch.sh` のコマンドはactive nameを持たないため、**既定では毎回unfilteredで起動し、その瞬間から取り合いが復活する。**

**恒久対処は未実施。** 本来の直しはrosterから不要な登録を落とすことである。

- `homelab/implementer` と `homelab/reviewer` の `claude-code` 登録 — ADR-015でClaude Codeはこの2役を起こさない
- ADR-013期の実験名14件(`auditor*` / `reviewer_*` / `tester*`)— いずれも `claude-code` 単独で競合相手はいないが、購読集合を膨らませる

**`leave.sh` は `<team> <agent_id>` しか取らず、登録単位で落とせない**(agentごと退会し、その退会イベントはquoryへ同期されるrosterへ入る)。登録の実体は上記 `registrations` 配列であり、どう落とすかは別途判断する。

## 反対方向の同じ危険(この調査で判明、未発火)

**`homelab-ops/coordinator` も `codex` と `claude-code` の両方に登録されており、codexのbridge(pid 678577)が生きてarmされている。** Operatorからの返信(OPRES)はこのペアへ届くため、**Codexのスレッドが先に取る経路が実在する。** そのbridgeのログに `wakeup` は1件も無く、これまで発火した証拠はない。

`docs/ai/status.md` の「いまcoordinatorを名乗る主体は無い」は、**bridgeが生きている点で現物と食い違う。**

## 当面の運用

**Coordinatorのwatcherは `actas coordinator` で起動する。** hookが渡す既定のコマンドはunfilteredなので、セッション開始のたびに取り直す。取れていない間は、送信のたびに `wakeup N` が増えたかを確認し、増えていなければその場でペインへ `history.sh` を読ませる。
