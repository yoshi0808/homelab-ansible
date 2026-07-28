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

**次に着手する順**に並べる。

| # | 項目 | 現在地 | 次にやること |
|---|---|---|---|
| 1 | **障害の自動捕捉(Step 1)** — Operator役の第一歩 | Tier 4 + W6(Tier 3)。**実装完了・本番稼働中**。T1の本番初回実行を2026-07-28に実機確認済み(`controller: quory` / `tester_mode: false` のspoolレコード実物)。T1(`roles/common_slack/tasks/capture.yml`)と収集器(`roles/incident_capture/`、quoryでtimer 5分間隔)が動作。W5/W6の全ACがPASS | ①**R8(Semaphore外ジョブの保険)が未実装**。②シェルとPythonで staged mode 取得を二重実装している負債の解消。③**Step 2**(ansy側で `claude -p` が第一報を起票)は未着手。**要件に「既知条件の除外」を含めること** — pve1の夏季平日シャットダウン運用により、Proxmox HW check / healthcheck が平日ごとに通知を出す(2026-07-27 Yoshinobu、既知として対象外と判断)。**捕捉は止めず起票側で弾く**(証拠は安く、いつか普段と違う症状が出たときの比較対象になる)。素通しにすると平日毎日Incidentが自動起票され、`原因分類` タグの母数が埋まって月次の昇格判断が狂う。**実測(2026-07-28)**: 現存バンドル41件のうち**約19〜20件(46〜49%)がpve1平日シャットダウン由来**(Proxmox healthcheck / hardware check / Time sync check、平日05:40-05:50 JSTに集中)。**弾く必要量はほぼ半分**という規模感で設計する。一次記録 `docs/ai/reviews/incident_auto_capture/2026-07-28_031_production_status_check.md` |

## Watch(観測待ち)

着手すべき作業ではなく、**将来の時点でしか確かめられないこと**を置く。

| 項目 | 発火条件 | 検証手段 | 一次記録 | 最終確認 |
|---|---|---|---|---|
| quoryの作業ツリーを**Testerが直接確認できない** | 次にquoryの作業ツリー状態を検証したいとき | Tester接続identity(`ann`)とリポジトリ所有者(`yoshi`)が異なり、gitの `dubious ownership` ガードが `rc=128` で拒否する。回避には `safe.directory` 設定が要り、今回は承認範囲外として構造的推論で代替した。**AC6(作業ツリーを汚さない)のquory側継続確認が原理的に盲目**である | 同上「未実施とその理由」 | 2026-07-27 |
| 月次Knowledge振り返りの**初回無人実行** | 毎月26日 07:15 JST(期日の正本はauto-memory `MEMORY.md` 先頭行。ここへ日付を写さない) | ansyで `systemctl list-timers ansible-knowledge-review.timer` と `journalctl -u ansible-knowledge-review`。実行後は作業ツリーに未commit差分が出る | `roles/knowledge_review/`、`playbooks/knowledge_review.yml`、`docs/ai/memory-classification.md`「月次振り返りの対象と手順」 | 2026-07-27 |
| weekly full patchの**apply gateを実データで通す**(AC5) | Proxmox dry-runが `PATCH_READY` を返す週 | `playbooks/proxmox_patch_weekly_full.yml` L159-188。`_dryrun_missing_nodes` が実データで空になり、両ノード揃ってgateを通ることを確認する。現状の根拠はdecoy検証のみ | `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_005_test_result.md` L426(§14-5の項目c) | 2026-07-27 |
| Reviewer / Testerの **effort=medium 試行** | 次にTier 4を回すとき | そのTier 4案件でfindings品質(逐行照合の取りこぼし)が落ちていないか。落ちていれば `.claude/agents/reviewer.md` / `tester.md` の `effort:` を `high` へ戻す | `docs/ai/role-routing-index.md`「モデル・effort配分(2026-07-26確定)」 | 2026-07-27 |
| Alloy **Phase 3(異常値のFire)** | Lokiにログが十分蓄積した時点 | requirementは作成済みで、閾値を決める実データ待ち。Grafana Exploreで対象シグネチャの出現頻度を見て判断する | `docs/ai/reviews/promtail_to_alloy/2026-07-19_phase3_alerting_requirement.md` | 2026-07-27 |
| Proxmoxパッチ自動チェーンの **実発火の観測** | パッチ件数が少なくYoshinobuの手動介入が要らない週末 | 自動チェーンが最後まで通ったログ。過去2回(2026-07-11/12、07-18/19)はいずれも大量パッチでYoshinobuが手動対応したため、チェーン全体の実発火はまだ観測できていない | `docs/ai/reviews/tester_mode/`、`docs/ai/context/operations/proxmox-patch.md` | 2026-07-27 |

## Next(着手候補)

着手可能だが、まだ始めていないもの。優先順位の議論は `skills/goal-tracking/SKILL.md`。

| 項目 | 内容 | 根拠 |
|---|---|---|
| **`1+R` に計画査読だけを足す形を認めるか** | `skills/delegation-tier/SKILL.md` は「Tier 1/2に査読を任意に足す形は無い。足したくなったらTier判定が誤っている信号」と定める。しかし2026-07-28の実測では、上流55 `tool_uses`(計画25+査読30)で**実装前に5件**が潰れ、うち1件は**Coordinator自身が書いたrequirementの内部矛盾**だった。`1+R` の工程には計画を見る者が誰も居ない。規範文書の新設のように**選定と正本整合が支配的な案件**に限って認めるかを判断する。**現行規定は維持しており、この起票は見直しの検討である** | `docs/ai/reviews/subagent_briefing/2026-07-28_003_plan_review.md`(検出5件の内訳)、同 `progress.md`「クローズ判断」、`docs/ai/effort-baseline.md`「2026-07-28(2件目)」 |
| **Auditorの起動条件と `status.md` 検査の矛盾** | `docs/ai/roles/coordinator.md` はAuditorを「`docs/ai/status.md` の該当行を消す**前**」に起動すると定め、`docs/ai/role-context-matrix.md` は「status.md の該当行が案件の現況と一致しているか」をAuditorの検査項目に置く。**両方を守るとこの指摘は毎回発火し、空振りと本物を区別できない。** 2026-07-28の初回で実際に発火した(そのときは実質も伴っていた)。起動条件と検査項目のどちらを直すか | `docs/ai/reviews/subagent_briefing/2026-07-28_007_audit.md` 指摘1、同 `progress.md`「Auditorの指摘と対応」 |
| **計画査読の正本に足りない2点** | ①**申告の妥当性に疑義が出たときの扱い**が層1/層2のどちらに属するか正本に無い(2026-07-28の初回で実際に発生。査読者が裁量で「層1は申告どおり通過、実質はCoordinatorのゲートへ」と分けた)②**査読者の出力の型が無い**(`skills/code-review/SKILL.md` はReviewer用で粒度が合わない)。いずれも `docs/ai/roles/techlead.md`「計画査読」の改訂になる | `docs/ai/reviews/subagent_briefing/2026-07-28_003_plan_review.md` §4-1・§4-4(初回実施者による報告) |
| **Auditorの単位分類が `effort-baseline.md` に無い** | 「実行単位」の定義がImplementer / Reviewer / Testerで、2026-07-28新設のAuditorがどちらにも属さない。**計画査読が層1基準(80 `tool_uses`)を実際に適用できなかった。** 本案件では参考値25(実績22)で影響が無かったが、Auditorへ重い検査を課す案件では基準の空白がそのまま効く | `docs/ai/effort-baseline.md`「採用する単位」にAuditorの記載が無いこと。`docs/ai/reviews/subagent_briefing/2026-07-28_003_plan_review.md` §4-3 |
| **ADRの `Status` を実態へ揃える** | 全5件が `Status: Proposed` のままである。**001(unifi_backup_fetch)と002(proxmox_patch_dryrun)は対応が完了済み**(2026-07-28 Yoshinobu確認)。**003〜005(incident capture系)は本件の対応完了時にまとめて更新できる**見込み。Tier 1で処理できる | `docs/ai/adr/` 各ファイル冒頭の `**Status:**` 行。2026-07-28 Yoshinobu明示 |
| `docs/ai/context-classification.md` の `## 6.` 重複 | 同ファイルに `## 6.` で始まる節が2つある(「完了条件の確認」と「Skillの配置とCodex/Claude Codeへの公開方法」)。節番号で参照すると誤った節へ着地する。**Tier 1で処理できる** | 同ファイルの現物。`docs/ai/reviews/subagent_briefing/2026-07-28_002_plan.md` §7 疑義#2(計画査読が現物確認済み) |
| Operator役の新設 | 現行6役(Coordinator / Tech Lead / Implementer / Reviewer / Tester / **Auditor**)は**開発工程しか持たず、運用工程が空白**である。Incident記録・運用レポートをAIへ委ねる方向。着手時期は未定 | `docs/ai/roles/` に運用工程のRoleが存在しないこと。Yoshinobu表明(2026-07-26) |
| 時刻表記JST規約をrepoへ明文化 | 「リポジトリの時刻表記はJST(+09:00)、`date -u`やローカル時刻+リテラル`Z`は詐称バグ」という規約が、repo内には `autonomous_recovery_policy.md` L174(通知文言の1行)しか無く、規約本体はCoordinatorのauto-memoryにある。Implementerが従うべき規約なのでrepo側が正本であるべき。障害バンドルがSemaphoreのUTCとreportsのJSTを混在させるため、実害が出る前に片付ける | `grep -rn "JST" docs/` の結果が通知文言1件のみであること。`docs/ai/memory-classification.md` 第0段(subagentの判断が変わる知識はrepoへ) |
| 収集器へ「消費済みidの記憶」防御を入れるか | 現在「消費済み」の正本は「spoolファイルが存在しないこと」の1つ。state.jsonにも記録する二重化は、両者が食い違う新しい欠陥クラスを生むため2026-07-28の案件では**意図的に見送った**。検出自体は `collection_errors` + exit 2 + systemd `failed` で既に効いている(今回の欠陥もそれで見つかった) | `docs/ai/reviews/incident_auto_capture/2026-07-28_018_acl_mask_plan.md` D7 |
| ACL付きパスへのchmodをpre-commitで自動検査するか | 「named-user ACLを持つパスへ `mode:` を指定していないか」を機械検査したいが、**検査対象がパス変数の解決を要する**(書き手が `incident_capture_spool_dir` 等の変数を経由するため、パス文字列のgrepでは現に壊れている箇所を1件も拾えないことが実証済み)。静的検査では偽陰性が確実に出る。**効かない検査は「掃引済み」という誤った安心を生む**ため見送った | 同上 D9、および §5の実証 |
| リポジトリ直下 `AGENTS.md` の要否判断 | Codexが開発工程から外れた結果、このファイルを読む主体が現状存在しない。残すか消すかが未判断。ファイル自身が末尾でそう述べている | `AGENTS.md` L7。規律1により状態は使う場所(当該ファイル)に書かれているが、**そこを開く動機を持つ人がいない**ため、判断の起票だけをここに置く |

## 載せていないもの(判断の記録)

規律2により、次は意図的にこのファイルへ載せていない。再度追加しようとしたときのために理由を残す。

- **proxmox_patch_dryrun AC4(両ノード同時到達不能)の実地検証** — 検証にはpve2の停止が必要で許可範囲外。観測待ちではなく残存リスクとして `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_005_test_result.md` L425(§14-5の項目b)に記録済み。
- **pve1の夏季平日シャットダウン運用** — 影響先である `roles/recovery_probe/defaults/main.yml` の `recovery_probe_pve_host` に、暫定である旨と復帰条件がコメントで書かれている。規律1により使う場所の記載を正とする。
