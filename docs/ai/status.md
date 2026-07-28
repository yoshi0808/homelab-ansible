# 現在地(status)

状態: **正本**(2026-07-27新設)

このファイルは「**今どこにいて、何を待っているか**」の正本である。規範(どう振る舞うか)はここに書かない。対話セッションは `/clear` のたびに文脈を失うが、このファイルとgitの現物があれば現在地を復元できる状態を保つ。

## このファイルの規律

1. **状態は「使う場所」へ書くのが第一選択。** コード・Policy・Contextの当該箇所に書けば、そこを変更する人の目に必ず入る(例: `roles/recovery_probe/defaults/main.yml` の `recovery_probe_pve_host`)。**ここへ載せるのは置き場が他に無い状態だけ** — 将来の日付やイベント待ち、複数箇所にまたがるもの。
2. **Watchの各行に検証手段を必須とする。** 書けない項目は載せず、残存リスクとして一次記録へ残し、「載せていないもの」へ1行残す。Nextは検証手段の代わりに**根拠**を必須とする。
3. **完了したら行を消す。** 履歴は `git log` が持つ。積み増すとこのファイル自身が「いちばん古いのに確実に読まれる層」になる(`docs/ai/memory/lessons/always-loaded-summaries-are-the-least-current.md`)。
4. **値を二重に持たない。** 他に正本があるものは参照だけ書く。
5. **更新のトリガは3つ** — 完了した / 方針を変えた / 観測待ちが増えた。

**このファイルも古くなりうる。** 3トリガはCoordinatorセッションを経由しない変化(Yoshinobuの手作業、外部システムの変化)を拾えず、補いは①案件やレビューの過程で気づいたらその場で消す②月次Knowledge振り返りが現物と突き合わせる、の2つで周期は最長1か月ある。**各行は「主張」ではなく「検証手段つきの申し送り」として読み、判断に使う前に検証手段の側を確かめること。**

`skills/goal-tracking/SKILL.md` の Now / Next / Later とは軸が違う(あちらは優先度軸、ここの Watch は時間・イベント軸)。優先度の議論が要る項目は Next に置く。

## Now(進行中)

| # | 項目 | 現在地 | 次にやること |
|---|---|---|---|
| 1 | **障害の自動捕捉・評価** — Operator役の第一歩 | **Policyを策定済み**(`docs/ai/policies/incident_capture_policy.md`、2026-07-28 Yoshinobu承認)。パイプラインは3段(捕捉=quory → 転送 → 評価=ansy)で、**捕捉は本番稼働中**。残り2段のrequirementを確定済み(`.../incident_auto_capture_step2/2026-07-28_006_step2_requirement.md`、Tier 4)。案件記録は `docs/ai/reviews/incident_auto_capture/`(Step 1、クローズ済み)と `docs/ai/reviews/incident_auto_capture_step2/`(現行) | **Tech Leadへ渡して分解・見積もり・ADR-005改訂**(requirement §12)。**未決の一覧はPolicy §8とrequirement §9が正本**(ここへ写さない)。**期限は2026-08-26の月次timer発火**(requirement §11) |

**2026-07-28にYoshinobuが決めた2点**(requirement §4 D-2・D-3・D-4が正本。ここは所在を示すだけ)。①評価結果は**repo内のgitignore済みパス**へ出し、`docs/ai/memory/incidents/` への昇格は人が行う → **ADR-005 Decision (1)・(4)「作業ツリーの外」は改訂される** ②月次 `claude -p` へ **`Read(reports/incidents/**)` の追加を承認**(IC-019)。拡大はこの1エントリのみ。

**OQ5(自動起票が作業ツリーを汚し月次評価を止める)は、IC-007で書き手が月次評価自身だけになったため実質解消した。** 書込が清潔チェックの後に起きるため、`roles/knowledge_review/tasks/main.yml:44-51` が既に許容する「先月分が未commitなら止まる」以上の新しい衝突は生じない。**この判断は未検証であり、ADR-005改訂時にTech Leadが現物で反証すること。**

**Step 1の残件2つは、使う場所へ書かず現状ここにしか無い**(規律1の例外として明示する)。①**R8(Semaphore外ジョブの保険)が未実装** ②シェルとPythonで staged mode 取得を**二重実装**している負債。一次記録は `docs/ai/reviews/incident_auto_capture/`。

## Watch(観測待ち)

**将来の時点でしか確かめられないこと**を置く。着手すべき作業ではない。

| 項目 | 発火条件 | 検証手段 | 一次記録 | 最終確認 |
|---|---|---|---|---|
| quoryの作業ツリーを**Testerが直接確認できない** | quoryの作業ツリー状態を検証したいとき | Tester接続identity(`ann`)と所有者(`yoshi`)が異なり `dubious ownership` が `rc=128` で拒否する。回避には `safe.directory` が要り承認範囲外。**AC6のquory側継続確認が原理的に盲目**。2026-07-28にも再発 | `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_005_test_result.md`、`.../incident_auto_capture_step2/2026-07-28_004_quory_units_survey.md` | 2026-07-28 |
| 月次Knowledge振り返りの**初回無人実行** | 毎月26日(期日の正本はauto-memory `MEMORY.md` 先頭行。ここへ写さない) | ansyで `systemctl list-timers ansible-knowledge-review.timer` と `journalctl -u ansible-knowledge-review`。実行後は作業ツリーに未commit差分が出る | `roles/knowledge_review/`、`docs/ai/memory-classification.md` | 2026-07-27 |
| weekly full patchの**apply gateを実データで通す**(AC5) | Proxmox dry-runが `PATCH_READY` を返す週 | `playbooks/proxmox_patch_weekly_full.yml` L159-188。`_dryrun_missing_nodes` が実データで空になること。現状の根拠はdecoy検証のみ | `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_005_test_result.md` L426 | 2026-07-27 |
| Reviewer / Testerの **effort=medium 試行** | 次にTier 4を回すとき | findings品質(逐行照合の取りこぼし)が落ちていないか。落ちていれば `.claude/agents/reviewer.md` / `tester.md` の `effort:` を `high` へ戻す | `docs/ai/role-routing-index.md`「モデル・effort配分」 | 2026-07-27 |
| Alloy **Phase 3(異常値のFire)** | Lokiにログが十分蓄積した時点 | requirementは作成済み。Grafana Exploreで対象シグネチャの出現頻度を見て閾値を決める | `docs/ai/reviews/promtail_to_alloy/2026-07-19_phase3_alerting_requirement.md` | 2026-07-27 |
| Proxmoxパッチ自動チェーンの **実発火の観測** | パッチ件数が少なく手動介入が要らない週末 | 自動チェーンが最後まで通ったログ。過去2回(07-11/12、07-18/19)は大量パッチで手動対応となり未観測 | `docs/ai/reviews/tester_mode/`、`docs/ai/context/operations/proxmox-patch.md` | 2026-07-27 |

## Next(着手候補) — 工程・体制

2026-07-28のTier 3案件(`docs/ai/reviews/subagent_briefing/`)で、新体制を初めて通した結果として出た未決。

| 項目 | 内容 | 根拠 |
|---|---|---|
| **`1+R` に計画査読だけを足す形を認めるか** | `skills/delegation-tier/SKILL.md` は「Tier 1/2に査読を足す形は無い。足したくなったらTier判定が誤っている信号」と定める。しかし上流55 `tool_uses` で**実装前に5件**が潰れ、うち1件は**Coordinator自身が書いたrequirementの内部矛盾**だった。`1+R` には計画を見る者が居ない。**現行規定は維持しており、この起票は見直しの検討** | `.../subagent_briefing/2026-07-28_003_plan_review.md`、同 `progress.md`「クローズ判断」 |
| **Auditorの起動条件と `status.md` 検査の矛盾** | `docs/ai/roles/coordinator.md` はAuditorを「該当行を消す**前**」に起動すると定め、`docs/ai/role-context-matrix.md` は「該当行が現況と一致しているか」を検査項目に置く。**両方を守るとこの指摘は毎回発火し、空振りと本物を区別できない** | `.../subagent_briefing/2026-07-28_007_audit.md` 指摘1 |
| **計画査読の正本に足りない2点** | ①申告の妥当性に疑義が出たときの扱いが層1/層2のどちらか不明(初回で実際に発生し、査読者が裁量で分けた)②査読者の出力の型が無い。いずれも `docs/ai/roles/techlead.md` の改訂 | `.../subagent_briefing/2026-07-28_003_plan_review.md` §4-1・§4-4 |
| **Auditorの単位分類が `effort-baseline.md` に無い** | 「実行単位」の定義がImplementer / Reviewer / Testerのみで、Auditorがどちらにも属さない。**層1基準(80 `tool_uses`)を実際に適用できなかった** | `docs/ai/effort-baseline.md`「採用する単位」、`.../subagent_briefing/2026-07-28_003_plan_review.md` §4-3 |
| Operator役の新設 | 現行6役は**開発工程しか持たず運用工程が空白**。Incident記録・運用レポートをAIへ委ねる方向。着手時期は未定 | `docs/ai/roles/` に運用工程のRoleが無いこと。Yoshinobu表明(2026-07-26) |
| リポジトリ直下 `AGENTS.md` の要否判断 | Codexが開発工程から外れ、このファイルを読む主体が存在しない。**そこを開く動機を持つ人がいない**ため起票だけをここに置く | `AGENTS.md` L7 |

## Next(着手候補) — システム・運用

| 項目 | 内容 | 根拠 |
|---|---|---|
| 時刻表記JST規約をrepoへ明文化 | 規約本体がCoordinatorのauto-memoryにあり、repo内は `autonomous_recovery_policy.md` L174(通知文言の1行)のみ。Implementerが従うべき規約なのでrepo側が正本であるべき。**障害バンドルがSemaphoreのUTCとreportsのJSTを混在させる**ため実害が出る前に片付ける | `grep -rn "JST" docs/` が通知文言1件のみ。`docs/ai/memory-classification.md` 第0段 |
| **ADRの `Status` を実態へ揃える** | 全5件が `Proposed` のまま。**001・002は対応完了済み**(2026-07-28 Yoshinobu確認)。**003〜005は本件の完了時にまとめて更新できる**見込み。Tier 1 | `docs/ai/adr/` 各ファイルの `**Status:**` 行 |
| `docs/ai/context-classification.md` の `## 6.` 重複 | `## 6.` で始まる節が2つあり、節番号で参照すると誤った節へ着地する。Tier 1 | 同ファイルの現物 |
| 収集器へ「消費済みidの記憶」防御を入れるか | 「消費済み」の正本は「spoolファイルが存在しないこと」の1つのみ。state.jsonへの二重化は**両者が食い違う新しい欠陥クラス**を生むため意図的に見送った。検出は `collection_errors` + exit 2 + systemd `failed` で効いている | `.../incident_auto_capture/2026-07-28_018_acl_mask_plan.md` D7 |
| ACL付きパスへのchmodをpre-commitで検査するか | **検査対象がパス変数の解決を要する**ため、パス文字列のgrepでは現に壊れている箇所を1件も拾えないことが実証済み。**効かない検査は「掃引済み」という誤った安心を生む**ため見送った | 同上 D9 |

## 載せていないもの(判断の記録)

規律2により意図的に載せていない。再度追加しようとしたときのために理由を残す。

- **proxmox_patch_dryrun AC4(両ノード同時到達不能)の実地検証** — pve2の停止が必要で許可範囲外。残存リスクとして `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_005_test_result.md` L425 に記録済み。
- **pve1の夏季平日シャットダウン運用** — `roles/recovery_probe/defaults/main.yml` の `recovery_probe_pve_host` に暫定である旨と復帰条件がある。規律1により使う場所の記載を正とする。
- **既知条件由来の捕捉が全体に占める割合(実測値)** — `docs/ai/policies/incident_capture_policy.md` IC-022 が正本。規律4により値をここへ写さない。
