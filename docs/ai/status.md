# 現在地(status)

状態: **正本**(2026-07-27新設)

このファイルは「**今どこにいて、何を待っているか**」の正本である。規範(どう振る舞うか)は `docs/ai/core.md` 以下が正本であり、ここには書かない。

対話セッションは `/clear` のたびに文脈を失うが、このファイルとgitの現物があれば現在地を復元できる状態を保つ。読者はCoordinator(対話セッション)、Yoshinobu、および必要に応じてsubagentである。

## このファイルの規律

1. **状態は「使う場所」へ書くのが第一選択。** コード・Policy・Contextの当該箇所に書けば、そこを変更する人の目に必ず入る。良い例は `roles/recovery_probe/defaults/main.yml` の `recovery_probe_pve_host: pve2` で、暫定である理由と復帰条件が変数のすぐ上にある。**このファイルへ載せるのは、使う場所が存在しない状態だけ** — 将来の日付やイベントを待つもの、複数箇所にまたがり単一の置き場が無いものに限る。
2. **Watchの各行に検証手段(パスまたはコマンド)を必須とする。** 書けない項目はWatchに載せない。検証手段が許可範囲外のものは「観測待ち」ではなく**残存リスク**であり、一次記録(`docs/ai/reviews/<target>/`)に残す。**このとき「載せていないもの」節へ必ず1行残す** — 除外を黙って行うと、このファイルを読んでも現在地が復元できなくなり、規律2自体が漏れの経路になる。Next(着手候補)は着手前で検証すべき事象がまだ無いため、検証手段の代わりに**根拠**(なぜ着手候補と言えるか)を必須とする。
3. **完了したら行を消す。** 履歴は `git log` が持つ。完了済みをここへ積み増すと、このファイル自身が「いちばん古いのに確実に読まれる層」になる(`docs/ai/memory/lessons/always-loaded-summaries-are-the-least-current.md`)。
4. **期日・設定値を二重に持たない。** 他に正本があるものは参照だけ書き、値を写さない。
5. **更新のトリガは3つ** — 「完了した」「方針を変えた」「観測待ちが増えた」。このいずれかが起きたセッションでは、終わる前にこのファイルを更新する。

**この3トリガはCoordinatorセッションを経由しない変化を拾えない**(Yoshinobuが手動で片付けた、外部システムの状態が変わった等)。つまりこのファイルも、程度は小さいが規律3が警戒しているのと同じ古さを抱えうる。補いは2つで、①Tier 3/4案件やレビューの過程で古い行に気づいたらその場で消す、②月次Knowledge振り返りが各行を現物と突き合わせる(`docs/ai/memory-classification.md`「状態の突合」)。**それでも周期は最長1か月あるため、この表の行は「主張」ではなく「検証手段つきの申し送り」として読むこと** — 判断に使う前に検証手段の側を確かめる。

`skills/goal-tracking/SKILL.md` の Now / Next / Later とは**軸が違う**。あちらは優先度軸、ここの Watch は時間・イベント軸である。Watch に Later 相当は無く、優先度の議論が要る項目は Next に置いてgoal-trackingを使う。

## Now(進行中)

| 項目 | 現在地 | 次にやること |
|---|---|---|
| **障害の自動捕捉・第一報起票**(Operator役の第一歩) | Tier 4。設計合意(D1〜D7)→ requirement(AC1〜AC7)→ Tech Lead調査+ADR-003/004 → **W0先行観測まで完了**。OQ1〜OQ6すべて解決済み。`homelab-semaphore-query task-time` をカタログへ追加しquoryへ配備済み。**本体の実装はまだ無い** | W1(Implementer A: `notify.yml` へのT1挿入)。工程は `2026-07-27_003_investigation.md` §8 の W0→W5 が正本。**AC1のベースラインは取得済み**(`recovery_probe_notify.yml`、rc=0 / ok=3 changed=0 failed=0 ignored=0) |

## Watch(観測待ち)

着手すべき作業ではなく、**将来の時点でしか確かめられないこと**を置く。

| 項目 | 発火条件 | 検証手段 | 一次記録 | 最終確認 |
|---|---|---|---|---|
| SessionStart hookの**実発火**(`scripts/session-context.sh`) | 次に`/clear`・再起動・compactが起きたとき | セッション冒頭の文脈に「セッション開始時の現在地」ブロックが載るか。載らなければ設定変更がwatcherに拾われていないので`/hooks`を一度開くか再起動する。スクリプト単体実行は検証済みで、未検証なのはイベント経由の発火のみ | `.claude/settings.json` の `hooks.SessionStart`、`docs/ai/reviews/session_continuity/2026-07-27_001_review.md` の未確認事項 | 2026-07-27 |
| 月次Knowledge振り返りの**初回無人実行** | 毎月26日 07:15 JST(期日の正本はauto-memory `MEMORY.md` 先頭行。ここへ日付を写さない) | ansyで `systemctl list-timers ansible-knowledge-review.timer` と `journalctl -u ansible-knowledge-review`。実行後は作業ツリーに未commit差分が出る | `roles/knowledge_review/`、`playbooks/knowledge_review.yml`、`docs/ai/memory-classification.md`「月次振り返りの対象と手順」 | 2026-07-27 |
| weekly full patchの**apply gateを実データで通す**(AC5) | Proxmox dry-runが `PATCH_READY` を返す週 | `playbooks/proxmox_patch_weekly_full.yml` L159-188。`_dryrun_missing_nodes` が実データで空になり、両ノード揃ってgateを通ることを確認する。現状の根拠はdecoy検証のみ | `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_005_test_result.md` L426(§14-5の項目c) | 2026-07-27 |
| Reviewer / Testerの **effort=medium 試行** | 次にTier 4を回すとき | そのTier 4案件でfindings品質(逐行照合の取りこぼし)が落ちていないか。落ちていれば `.claude/agents/reviewer.md` / `tester.md` の `effort:` を `high` へ戻す | `docs/ai/role-routing-index.md`「モデル・effort配分(2026-07-26確定)」 | 2026-07-27 |
| Alloy **Phase 3(異常値のFire)** | Lokiにログが十分蓄積した時点 | requirementは作成済みで、閾値を決める実データ待ち。Grafana Exploreで対象シグネチャの出現頻度を見て判断する | `docs/ai/reviews/promtail_to_alloy/2026-07-19_phase3_alerting_requirement.md` | 2026-07-27 |
| Proxmoxパッチ自動チェーンの **実発火の観測** | パッチ件数が少なくYoshinobuの手動介入が要らない週末 | 自動チェーンが最後まで通ったログ。過去2回(2026-07-11/12、07-18/19)はいずれも大量パッチでYoshinobuが手動対応したため、チェーン全体の実発火はまだ観測できていない | `docs/ai/reviews/tester_mode/`、`docs/ai/context/operations/proxmox-patch.md` | 2026-07-27 |

## Next(着手候補)

着手可能だが、まだ始めていないもの。優先順位の議論は `skills/goal-tracking/SKILL.md`。

| 項目 | 内容 | 根拠 |
|---|---|---|
| Operator役の新設 | 現行5役(Coordinator / Tech Lead / Implementer / Reviewer / Tester)は**開発工程しか持たず、運用工程が空白**である。Incident記録・運用レポートをAIへ委ねる方向。着手時期は未定 | `docs/ai/roles/` に運用工程のRoleが存在しないこと。Yoshinobu表明(2026-07-26) |
| 時刻表記JST規約をrepoへ明文化 | 「リポジトリの時刻表記はJST(+09:00)、`date -u`やローカル時刻+リテラル`Z`は詐称バグ」という規約が、repo内には `autonomous_recovery_policy.md` L174(通知文言の1行)しか無く、規約本体はCoordinatorのauto-memoryにある。Implementerが従うべき規約なのでrepo側が正本であるべき。障害バンドルがSemaphoreのUTCとreportsのJSTを混在させるため、実害が出る前に片付ける | `grep -rn "JST" docs/` の結果が通知文言1件のみであること。`docs/ai/memory-classification.md` 第0段(subagentの判断が変わる知識はrepoへ) |
| リポジトリ直下 `AGENTS.md` の要否判断 | Codexが開発工程から外れた結果、このファイルを読む主体が現状存在しない。残すか消すかが未判断。ファイル自身が末尾でそう述べている | `AGENTS.md` L7。規律1により状態は使う場所(当該ファイル)に書かれているが、**そこを開く動機を持つ人がいない**ため、判断の起票だけをここに置く |

## 載せていないもの(判断の記録)

規律2により、次は意図的にこのファイルへ載せていない。再度追加しようとしたときのために理由を残す。

- **proxmox_patch_dryrun AC4(両ノード同時到達不能)の実地検証** — 検証にはpve2の停止が必要で許可範囲外。観測待ちではなく残存リスクとして `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_005_test_result.md` L425(§14-5の項目b)に記録済み。
- **pve1の夏季平日シャットダウン運用** — 影響先である `roles/recovery_probe/defaults/main.yml` の `recovery_probe_pve_host` に、暫定である旨と復帰条件がコメントで書かれている。規律1により使う場所の記載を正とする。
