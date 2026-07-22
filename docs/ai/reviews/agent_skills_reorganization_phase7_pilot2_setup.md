# Phase 7 pilot2最小セット: monitoring_healthcheck disk使用率チェック(無印trio)

作成日: 2026-07-22

要求元: homelab agmsg `claude` → `techlead`、2026-07-22T02:32:25Z。要旨は次の3点。

1. pilot1(`radius_healthcheck`、techlead2配下、`docs/ai/reviews/agent_skills_reorganization_phase7_pilot_setup.md`)は完了・Coordinator承認済み・commit `2026164`済みだが、techlead2固有のパターンでないか未確認。
2. 同じ枠組み(限定Context/Policy参照、軽量Skill評価、Role別手動読込順序)を、techlead配下(`implementer`/`reviewer`/`tester`、無印trio)で別の低リスク案件に対して回す。対象はradius_healthcheckの二番煎じでなく別role。
3. `docs/ai/reviews/agent_skills_reorganization_todo7-2_result.md`の改善候補を、可能な範囲で今回の依頼・setupへ反映する。

## 目的と範囲

このメモは、`roles/monitoring_healthcheck` へルートファイルシステムのdisk使用率チェックを追加する低リスク案件で、pilot1と同じ手動Role/Context/Policy/Skill選択の枠組みを、無印trioで再試行するための最小セットである。全面的なContext分割、正式Role定義、Skill導入、起動script変更は行わない。

pilot1との違い(意図的な設計判断):

- 担当trioがtechlead2配下でなくtechlead配下(無印)である。routingは`docs/ai/role-routing-index.md`のtrio routing節どおり、techlead2/2付きtrioと混在させない。
- 対象roleは`radius_healthcheck`でなく`monitoring_healthcheck`(監視スタックの死活・リソース監視)。ただし追加する指標はpilot1と同じ「ルートファイルシステムのdisk使用率」を選んだ。これはTODO 7-2で見つかった「`used_percent`の意味論を`used/total`と誤読みしやすい」という欠陥が、別roleの別Implementerでも再発しないか(＝受入条件に意味論を明記する改善が効くか)を直接確認するためである。
- `playbooks/monitoring_healthcheck.yml`の`tester-gate: safe-readonly`コメントは「`common_slack`の`tester_mode`ガードで抑止される」と書かれているが、現行`tasks/main.yml`の実guardは`skip_notifications`である(`tester_mode`は既に廃止済み)。これは`radius_healthcheck`で見つかったmarker driftと同型の事象が既にここにも存在する疑いがある。今回はReviewerに「理由文と実行経路を照合する」ことを明示指示し、TODO 7-2のReviewer Skill改善候補が独立に機能するかを確認する(答えを事前に教えない)。

## 受入条件

- `files/monitoring-healthcheck.sh`は、既存の`services`/`ports`/`memory`ブロックと並列に`disk`ブロックを追加する。ルートファイルシステム(`/`)の`total_bytes`/`used_bytes`/`available_bytes`/`used_percent`をバイト単位・整数percentで収集する。
- **意味論(明記): `used_percent`は`used_bytes / total_bytes`から自前計算せず、`df -B1 -P /`が返すUse%列をそのまま整数として採用する。** 予約領域(reserved blocks)や切り上げにより、単純な`used/total*100`とは異なる値になることがあるため、既存`memory.used_percent`(自前計算)のコピー&ペーストで実装しない。`radius_healthcheck`の対応する実装(`roles/radius_healthcheck/files/radius-healthcheck.sh`の`disk_used_percent`まわり)を実装前に読み、同じ収集方式を踏襲してよいかREVIEWで確認すること。
- 収集失敗時(`df`が異常終了、出力形式が想定外など)は`collection_ok: false`とし、他フィールドは安全なデフォルト値(0等)にする。既存`memory`ブロックの失敗時フォールバックと対称にする。
- `tasks/check.yml`は、既存の`monitoring_criticals`/`monitoring_warnings`ロジックと対称に、disk収集失敗をcritical、`used_percent`が80–89%をwarning、90%以上をcriticalとする(`memory`ブロックの閾値と同じ数値)。
- `monitoring_report`と`debug`メッセージへ、disk の `total_mb`/`used_mb`/`available_mb`/`used_percent`/`collection_ok` を、既存`memory`フィールドと同じ命名規則で追加する。
- `tasks/main.yml`は変更しない。レポート保存・Slack通知・fail分岐は既存どおり`check.yml`の結果を使う。
- `playbooks/monitoring_healthcheck.yml`の`tester-gate: safe-readonly`マーカーは変更しない。ただし、Reviewerはこのマーカーの理由文(「`tester_mode`ガードで抑止される」)と、`tasks/main.yml`の実際のguard(`skip_notifications`)が一致しているかを独立に確認し、不一致であれば指摘としてfollow-up(`docs/ai/reviews/monitoring_healthcheck/`への記録)へ残す。マーカー分類自体(`safe-readonly`の是非)は変更しない。
- 既存のservice、port、memory、report保存、Slack通知、fail挙動を壊さない。

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

新しいContextファイルは作らない。現在の事実は次から確認する。

| 対象 | 参照先 | 読む理由 |
|---|---|---|
| 対象groupとplaybook | `docs/ai/core.md`、`playbooks/monitoring_healthcheck.yml`、`inventories/homelab/hosts.yml`の`monitoring_servers`(monnieのみ) | 実行入口とtester-gate、対象ホストを確認する |
| 現行role構造 | `roles/monitoring_healthcheck/files/monitoring-healthcheck.sh`、`tasks/check.yml`、`tasks/main.yml`、`defaults/main.yml` | services/ports/memoryの既存対称パターンと責務境界を確認する |
| disk収集の参考実装 | `roles/radius_healthcheck/files/radius-healthcheck.sh`と`tasks/check.yml`のdisk関連部分 | `df` Use%を正本にする実装方式を確認する(意味論の再発防止) |
| 既存要求 | `docs/ai/reviews/monitoring_healthcheck/`配下の既存requirement/final(直近は`2026-06-09_007_final.md`) | 現行確定仕様を確認する。過去文書より現在のコードを優先する |
| 今回の要求 | Coordinatorからtechleadへの2026-07-22T02:32:25Z agmsg依頼と本メモ | disk追加の範囲・閾値・成果物・marker確認指示を確認する |

Inventoryの他host、他healthcheck role(`radius_healthcheck`のdisk実装部分を除く)、過去の中間review全文は、差分から必要性が生じない限り読まない。

## pilot用Policy参照

`docs/ai/core.md`を読んだ上で、詳細は`docs/ai/core-migration-map.md`の該当行から旧coreの正確な節だけを辿る。

| Policy | 参照先(core-migration-map ID) | この案件で守ること |
|---|---|---|
| shell / Ansible責務分離 | C07-01, C07-02(旧core §7、L261-263) | shellは収集とJSON整形だけ、判定・分類・reportはAnsible側。`status`や`warning`をshellに書かせない |
| tester-gate必須・分類 | C18-01, C18-11(旧core §18.1, §18.4) | `safe-readonly`を維持し、markerを削除・変更しない |
| testerの実行境界 | C18-12(旧core §18.5) | testerはmarkerと実guardを自分で確認し、安全な検証を選ぶ。`--check`なしのAPPLY相当実行はしない |
| 共通安全境界 | `docs/ai/core.md` | 秘密/IPを記載せず、既存変更を保護し、commit/pushしない |

本案件ではpatch、restart、reboot、migration、firewall、inventory変更を行わない。実ホスト実行が必要になった場合も、testerがmarkerと副作用を再評価する。

## 公開Skillの軽評価

pilot1と同じ結論を踏襲する。今回もdiffは小さく(既存roleへの1指標追加)、pilot1で評価した`code-review-and-quality`・`ansible-playbook-creator`はいずれも今回もscope不一致のため再評価不要と判断し、不採用のまま進める。新規候補の探索は行わない(Phase 4本格着手前のため)。

## 手動読込順序と成果物

成果物は`docs/ai/reviews/monitoring_healthcheck/`配下に、既存番号(`2026-06-09_007_final.md`まで)の続きとして`008`から採番する。

### implementer

1. `docs/ai/core.md`
2. `docs/ai/role-routing-index.md`のimplementer行とtrio routing
3. 本メモのContext / Policy参照のうち、現行role、disk収集の参考実装、既存final
4. Coordinatorの依頼と本メモの受入条件(特にdisk `used_percent`の意味論)
5. `git status`と対象ファイルの現在差分

実装後は`docs/ai/reviews/monitoring_healthcheck/2026-07-22_008_implement.md`に変更、自己検証(閾値境界79/80/89/90、収集失敗時のフォールバック、`df` Use%との比較)、未検証事項、読込プロセスの所感を記録してtechleadへ返す。

### reviewer

1. `docs/ai/core.md`
2. `docs/ai/role-routing-index.md`のreviewer行とtrio routing
3. 本メモのContext / Policy参照のうち、現行role、既存final
4. Coordinatorの依頼、本メモ、implement成果物、現在diff

`docs/ai/reviews/monitoring_healthcheck/2026-07-22_009_review.md`に重大度付き指摘、判定、読込プロセスの所感を記録してtechleadへ返す。原則としてコードは編集しない。

**追加指示(TODO 7-2反映)**: `playbooks/monitoring_healthcheck.yml`冒頭の`# tester-gate:`コメントの理由文と、`roles/monitoring_healthcheck/tasks/main.yml`の実際のSlack通知抑止guardを突き合わせ、一致しているか必ず報告する(一致・不一致いずれの結果でも記録すること)。

### tester

1. `docs/ai/core.md`
2. `docs/ai/role-routing-index.md`のtester行とtrio routing
3. 本メモのContext / Policy参照のうち、playbook marker、現行role
4. Coordinatorの依頼、本メモ、implement / review成果物、現在diff

まず`docs/ai/reviews/monitoring_healthcheck/2026-07-22_010_test_plan.md`に安全分類、静的・ローカル・実ホスト検証の境界を記録する。承認不要なread-only範囲で実施し、結果を`2026-07-22_011_test_result.md`に記録してtechleadへ返す。実ホスト実行を当然視せず、必要性と副作用を再評価する。可能であれば、pilot1のtester2が行ったlocalhost harness方式(source taskを副作用なしでfixture評価する)を踏襲する。

## pilotで観察すること

各Roleは成果物に次を短く記録する。

- 指定外のContextを読んだか。読んだ場合は理由。
- 必要な情報が不足したか。
- Tech Leadの指定が多すぎたか、少なすぎたか。
- 他Roleと責務が重複したか。
- 公開Skill不採用が妥当だったか。
- Incident / Lesson / DecisionとしてKnowledgeへ残すべき内容が生じたか。
- (今回追加) TODO 7-2の改善候補(意味論明記、marker理由と実guardの照合、原依頼traceability)が実際に効果があったか、なかったか。

完了後、techleadは実装/レビュー/テストの結果とプロセス観察をagmsgでCoordinator(`claude`)へ共有する。
