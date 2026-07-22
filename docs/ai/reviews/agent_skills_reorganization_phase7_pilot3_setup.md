# Phase 7 pilot3最小セット: proxmox_snapshot_check の critical閾値追加 + 新規Context作成の検証(無印trio)

作成日: 2026-07-22

要求元: homelab agmsg `claude` → `techlead`、2026-07-22T07:13:28Z。要旨は次の2点。

1. pilot1(`radius_healthcheck`、techlead2配下)・pilot2(`monitoring_healthcheck`、techlead配下)はいずれも既存`docs/ai/prompts/core.md`(現`docs/ai/core.md`)の節を指すだけで完結しており、**新しいContextファイルを実際に作る**状況を未検証。本格Phase2(System/Repository Context全面分割)へ進む前に、この軸を検証する。
2. 必須条件: setup作成時に新しく小さなContextファイルを最低1本実際に作成し、それがImplementer/Reviewer/Testerの判断にどう役立ったか(または過剰だったか)をprocess観察に含める。加えて、今日発生したProcess Incident(依頼B、`docs/ai/reviews/agent_skills_reorganization_phase7_process_incident_lightweight_lane.md`)を受けた「軽量レーン」の考え方を、pilot3の中でコメント/文書のみの小修正が発生した場合に試験適用する。

## 目的と範囲

このメモは、`roles/proxmox_snapshot_check` へ「非常に古いsnapshotをcriticalとして扱う」二段階閾値判定を追加する低リスク案件で、pilot1/2と同じ手動Role/Context/Policy/Skill選択の枠組みを、無印trioで再試行するための最小セットである。加えて、techleadが本setup作成時に新規Contextファイルを1本実際に作成した(`docs/ai/context/operations/healthcheck.md`)。全面的なContext分割、正式Role定義、Skill導入、起動script変更は行わない。

pilot1/2との違い(意図的な設計判断):

- 対象roleは`radius_healthcheck`・`monitoring_healthcheck`のどちらでもなく`proxmox_snapshot_check`(VM/CTスナップショットの陳腐化検知)。この役割は現状、staleと判定したsnapshotを一律`WARNING`にしか分類できず、warning/critical二段階を持たない。pilot1/2で見た「二段階閾値の意味論」パターン(`docs/ai/context/operations/healthcheck.md` §2)を、初めて`WARNING`のみのroleに適用したときに同じ設計判断(二段階目の意味、既存単一閾値の扱い)を再現できるかを見る。
- shellスクリプト(`proxmox-snapshot-collect.sh`)は収集専任(判定なし)であることが既にコメントで明記されており、変更不要。今回はAnsible側(`tasks/main.yml`・`defaults/main.yml`)のみの変更になる。shell変更が伴わない案件でも同じRole/Context/Policy枠組みが過不足なく機能するかを確認する。
- **新規Context**: `docs/ai/context/operations/healthcheck.md`を新規作成した。pilot1/2は「新しいContextファイルは作らない」と明記して既存core.mdの節参照のみで進めたが、今回は必須条件によりtechleadが実際に1本作成し、Implementer/Reviewer/Testerに読ませる。内容は健全性チェック系role共通の(1)shell/Ansible責務分離、(2)warning/critical二段階閾値の慣習、(3)tester-gateマーカーと実guardの整合、(4)report保存パターン、(5)意味論の自前計算に関する既知の落とし穴、の5点に限定した最小サブセットである。

## 受入条件

- `roles/proxmox_snapshot_check/defaults/main.yml`に、既存の`proxmox_snapshot_check_threshold_seconds`(warning相当、7日)と対称の新しい変数(例: `proxmox_snapshot_check_critical_threshold_seconds`、implementerが命名は判断してよいが`_seconds`単位・命名規則は既存変数に揃える)を追加する。デフォルト値はimplementerが妥当な値(例: 30日=2592000)を判断し、根拠を成果物に残す。
- `roles/proxmox_snapshot_check/tasks/main.yml`に、critical閾値以上に古いsnapshotを`stale_critical`(名称はimplementer判断)として分離し、`proxmox_snapshot_report.result.status`を`CRITICAL`/`WARNING`/`OK`の3値に拡張する。**意味論(明記): critical閾値はwarning閾値(7日)より長い期間でなければならない。critical該当のsnapshotはwarning側の一覧から二重計上せず、warning一覧はcritical未満・warning以上の範囲に限定する**(`monitoring_healthcheck`の`memory`/`disk`が80–89%をwarning、90%以上をcriticalとし重複させていないのと対称の設計)。
- 収集失敗(`collection_ok: false`または`errors`非空)は、既存どおり最低`WARNING`として扱う。今回の変更でcritical化はしない(収集失敗をcriticalへ格上げするかはスコープ外、implementerが判断に迷った場合はreviewerへ明示的にエスカレーションする)。
- Slack通知(`common_slack/notify.yml`呼び出し)は、`slack_status`を`proxmox_snapshot_report.result.status`に応じて`critical`/`warning`から選ぶよう拡張する(現状は`warning`固定)。`when`条件も`result.status == 'WARNING'`から`result.status in ['WARNING', 'CRITICAL']`等へ拡張する。
- `Semaphore`向けsummary text(`snapshot_check_summary_text`)は、`ns.result`の集計に`CRITICAL`を追加する(現状`OK`/`WARNING`の二値)。
- `playbooks/proxmox_snapshot_check.yml`の`tester-gate: safe-readonly`マーカーは変更しない。ただし、reviewerは念のためマーカー理由文と`common_slack/notify.yml`の実guardの整合を確認する(pilot1/2からの継続確認。既に依頼Bで文言統一済みのため、今回は不一致が出ない想定だが、実際に確認して記録する)。
- shellスクリプト(`proxmox-snapshot-collect.sh`)は変更しない。
- 既存の`stale_count`・`total_snapshots`・`collection_ok`・`errors`のレポートフィールドと、既存の7日warning判定を壊さない(後方互換のフィールドは残す)。

## Role / identity / routing

正本は`docs/ai/role-routing-index.md`をそのまま使う。

```text
techlead
  -> implementer -> techlead
  -> reviewer    -> techlead
  -> tester      -> techlead
  -> 結果を統合してCoordinator claudeへ共有
```

各Roleは同じファイルを無差別に読まず、下記の指定範囲だけを読む。2付きtrio(`implementer2`/`reviewer2`/`tester2`)への依頼・応援は行わない(role-routing-indexのcross-trio原則どおり)。

## pilot用Context参照

| 対象 | 参照先 | 読む理由 |
|---|---|---|
| 対象playbookと対象host | `docs/ai/core.md`、`playbooks/proxmox_snapshot_check.yml`、`inventories/homelab/hosts.yml`の`proxmox`group | 実行入口とtester-gate、対象ホストを確認する |
| 現行role構造 | `roles/proxmox_snapshot_check/files/proxmox-snapshot-collect.sh`、`tasks/main.yml`、`defaults/main.yml` | 収集/判定の責務境界、既存warning単一判定のロジックを確認する |
| **新規Context(必須)** | `docs/ai/context/operations/healthcheck.md` | healthcheck系role共通の二段階閾値慣習・marker整合・報告パターン・既知の落とし穴を確認する。今回のpilotで実際に役立ったか/過剰だったかを成果物に記録する |
| 二段階閾値の参考実装 | `roles/monitoring_healthcheck/tasks/check.yml`のdisk/memory二段階判定、`roles/proxmox_healthcheck/tasks/main.yml`のroot filesystem二段階判定 | warning/criticalの分離方法・重複計上の避け方を確認する |
| 既存要求 | `docs/ai/reviews/proxmox_snapshot_check/`配下の既存requirement/final(直近は`2026-06-17_005_review.md`) | 現行確定仕様を確認する。過去文書より現在のコードを優先する |
| 今回の要求 | Coordinatorからtechleadへの2026-07-22T07:13:28Z agmsg依頼と本メモ | critical閾値追加の範囲、新規Context作成の必須条件、process観察の追加項目を確認する |

Inventoryの他host、他healthcheck role(参考実装として指定した部分を除く)、過去の中間review全文は、差分から必要性が生じない限り読まない。

## pilot用Policy参照

`docs/ai/core.md`を読んだ上で、詳細は`docs/ai/core-migration-map.md`の該当行から旧coreの正確な節だけを辿る。

| Policy | 参照先(core-migration-map ID) | この案件で守ること |
|---|---|---|
| shell / Ansible責務分離 | C07-01, C07-02(旧core §7、L261-263) | shellは変更しない。判定ロジックはすべて`tasks/main.yml`側に置く |
| tester-gate必須・分類 | C18-01, C18-11(旧core §18.1, §18.4) | `safe-readonly`を維持し、markerを削除・変更しない |
| testerの実行境界 | C18-12(旧core §18.5) | testerはmarkerと実guardを自分で確認し、安全な検証を選ぶ。`--check`なしのAPPLY相当実行はしない |
| 共通安全境界 | `docs/ai/core.md` | 秘密/IPを記載せず、既存変更を保護し、commit/pushしない |

本案件ではpatch、restart、reboot、migration、firewall、inventory変更を行わない。実ホスト実行が必要になった場合も、testerがmarkerと副作用を再評価する。

## 公開Skillの軽評価

pilot1/2と同じ結論を踏襲する。今回もdiffは小さく(既存roleへの閾値1段追加、shell変更なし)、`code-review-and-quality`・`ansible-playbook-creator`はいずれも今回もscope不一致のため再評価不要と判断し、不採用のまま進める。新規候補の探索は行わない(Phase 4本格着手前のため)。

## 軽量レーンの試験適用について

pilot3自体はロジック変更(判定ロジック・Slack通知経路・summary集計の拡張)を含むため、軽量レーンの対象外であり、以下のフル無印trioフローで進める。ただし、作業中にコメント/文書のみの小さな修正(例: 既存コメントの文言微修正)が発生した場合は、`docs/ai/reviews/agent_skills_reorganization_phase7_process_incident_lightweight_lane.md`の軽量レーンの考え方(棚卸し1Role、複数ファイル同種変更は1バッチ、中間成果物を増やさない)を試験適用してよい。適用した場合は効果の手触りをprocess観察に記録する。

## 手動読込順序と成果物

成果物は`docs/ai/reviews/proxmox_snapshot_check/`配下に、既存番号(`2026-06-17_005_review.md`まで)の続きとして`006`から採番する。

### implementer

1. `docs/ai/core.md`
2. `docs/ai/role-routing-index.md`のimplementer行とtrio routing
3. 本メモのContext / Policy参照のうち、現行role、**新規Context(`docs/ai/context/operations/healthcheck.md`)**、二段階閾値の参考実装、既存final
4. Coordinatorの依頼と本メモの受入条件(特にwarning/critical重複計上の回避)
5. `git status`と対象ファイルの現在差分

実装後は`docs/ai/reviews/proxmox_snapshot_check/2026-07-22_006_implement.md`に、変更内容、選んだcritical閾値の根拠、自己検証(warning/critical/OK境界、collection失敗時の扱い、重複計上がないことの確認)、未検証事項、**新規Contextを読んだことが実装判断にどう役立ったか/過剰だったか**、読込プロセスの所感を記録してtechleadへ返す。

### reviewer

1. `docs/ai/core.md`
2. `docs/ai/role-routing-index.md`のreviewer行とtrio routing
3. 本メモのContext / Policy参照のうち、現行role、**新規Context**、既存final
4. Coordinatorの依頼、本メモ、implement成果物、現在diff

`docs/ai/reviews/proxmox_snapshot_check/2026-07-22_007_review.md`に重大度付き指摘、判定、**新規Contextが指摘の質・速度にどう影響したか**、読込プロセスの所感を記録してtechleadへ返す。原則としてコードは編集しない。

**追加指示**: `playbooks/proxmox_snapshot_check.yml`冒頭の`# tester-gate:`コメントの理由文と、`roles/common_slack/tasks/notify.yml`の実際のSlack通知抑止guardを突き合わせ、一致しているか必ず報告する(一致・不一致いずれの結果でも記録すること)。

### tester

1. `docs/ai/core.md`
2. `docs/ai/role-routing-index.md`のtester行とtrio routing
3. 本メモのContext / Policy参照のうち、playbook marker、現行role、**新規Context**
4. Coordinatorの依頼、本メモ、implement / review成果物、現在diff

まず`docs/ai/reviews/proxmox_snapshot_check/2026-07-22_008_test_plan.md`に安全分類、静的・ローカル・実ホスト検証の境界を記録する。承認不要なread-only範囲で実施し、結果を`2026-07-22_009_test_result.md`に記録してtechleadへ返す。実ホスト実行を当然視せず、必要性と副作用を再評価する。可能であれば、pilot1/2のtesterが行ったlocalhost source-task harness方式(source taskを副作用なしでfixture評価する)を踏襲し、warning/critical/OKの3値分類と重複計上なしを境界値で確認する。

## pilotで観察すること

各Roleは成果物に次を短く記録する。

- 指定外のContextを読んだか。読んだ場合は理由。
- 必要な情報が不足したか。
- Tech Leadの指定が多すぎたか、少なすぎたか。
- 他Roleと責務が重複したか。
- 公開Skill不採用が妥当だったか。
- Incident / Lesson / DecisionとしてKnowledgeへ残すべき内容が生じたか。
- **(今回必須) 新規Context(`docs/ai/context/operations/healthcheck.md`)が実際の判断にどう役立ったか、過剰だったか、不足していたか。**
- (該当すれば) 軽量レーンの考え方を試験適用した場合、その手触り。

完了後、techleadは実装/レビュー/テストの結果とプロセス観察をagmsgでCoordinator(`claude`)へ共有する。
