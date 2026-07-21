# Phase 7 pilot最小セット: radius_healthcheck disk使用率チェック

作成日: 2026-07-21

要求元: homelab agmsg `claude` → `techlead2`、2026-07-21T12:59:05Z。機能要件とpilot目的は、この依頼を本メモへ正規化した。

## 目的と範囲

このメモは、`roles/radius_healthcheck` へルートファイルシステムのdisk使用率チェックを追加する低リスク案件で、新しいRole / Context / Policy / Skill選択を手動で試すための最小セットである。全面的なContext分割、正式Role定義、Skill導入、起動script変更は行わない。

案件の受入条件:

- `files/radius-healthcheck.sh` は `df` からルートファイルシステムのsize / used / availableをバイト単位で収集し、予約領域と切り上げを反映した`df`のUse%を整数の`used_percent`としてJSONへ整形する。正常・warning・criticalの判定は行わない。
- `tasks/check.yml` はmemoryと対称にdisk収集失敗をcritical、used percent 80–89%をwarning、90%以上をcriticalとする。
- `tasks/check.yml` の `radius_report` とdebugへdiskの `total_mb` / `used_mb` / `available_mb` / `used_percent` / `collection_ok` を追加する。
- `tasks/main.yml` は既存どおり `check.yml` の結果を保存・通知・failへ渡す。disk判定やreport生成を重複実装しない。
- `playbooks/radius_healthcheck.yml` の `tester-gate: safe-readonly` は変更しない。
- 既存のservice、port、journal、memory、report、notification、fail挙動を壊さない。

## Role / identity / routing

正本は `docs/ai/role-routing-index.md` をそのまま使う。

```text
techlead2
  -> implementer2 -> techlead2
  -> reviewer2    -> techlead2
  -> tester2      -> techlead2
  -> 結果を統合してCoordinator claudeへ共有
```

各Roleは同じファイルを無差別に読まず、下記の指定範囲だけを読む。

## pilot用Context参照

新しいContextファイルは作らない。現在の事実は次から確認する。

| 対象 | 参照先 | 読む理由 |
|---|---|---|
| 対象groupとplaybook | `docs/ai/prompts/core.md` §4 L118–136、`playbooks/radius_healthcheck.yml` | `radius_servers` と実行入口、tester-gateを確認する |
| 現行role構造 | `roles/radius_healthcheck/files/radius-healthcheck.sh`、`tasks/check.yml`、`tasks/main.yml`、`defaults/main.yml` | memory収集・判定・reportの対称パターンと責務境界を確認する |
| 既存要求 | `docs/ai/reviews/radius_healthcheck/2026-05-06_001_requirements.md` | read-only、report保存、初回除外を確認する |
| 現行確定状態 | `docs/ai/reviews/radius_healthcheck/2026-05-09_015_final.md` と現在のコード | 過去文書より現在のコードを優先し、前回案件が確定済みであることを確認する |
| 今回の要求 | Coordinatorからtechlead2への2026-07-21 agmsg依頼と本メモ | disk追加の範囲・閾値・成果物を確認する |

Inventoryの値、他healthcheck role、過去の中間review全文は、差分から必要性が生じない限り読まない。

## pilot用Policy参照

| Policy | 参照先 | この案件で守ること |
|---|---|---|
| shell / Ansible責務分離 | `docs/ai/prompts/core.md` §6–7 L211–265 | shellは収集とJSON整形だけ、判定・分類・reportはAnsible側 |
| tester-gate | `docs/ai/prompts/core.md` §18.1 L1052–1071、§18.4–18.5 L1200–1227 | `safe-readonly`を維持し、testerはmarkerを自分で確認して安全な検証を選ぶ |
| 共通安全境界 | `docs/ai/core.md` | 秘密/IPを記載せず、既存変更を保護し、commit/pushしない |

本案件ではpatch、restart、reboot、migration、firewall、inventory変更を行わない。実ホスト実行が必要になった場合も、testerがmarkerと副作用を再評価する。

## 公開Skillの軽評価

少数候補だけを一次評価し、今回は導入しない。

| 候補 | 評価 | 判断 |
|---|---|---|
| `addyosmani/agent-skills` の `code-review-and-quality` | correctness / readability / architecture / security / performanceの汎用レビュー。Ansibleのshell責務分離、tester-gate、既存memory対称実装は扱わない | Reviewerの既存観点と重複し、この小差分では追加Contextのコストが上回るため不採用 |
| `claude-code-plugins-plus-skills` の `ansible-playbook-creator` | playbook新規作成向けの候補。今回は既存roleの3ファイルに対する小変更 | scopeが広く、既存設計へ合わせるpilot目的に適合しないため不採用 |

参照:

- https://github.com/addyosmani/agent-skills/blob/main/skills/code-review-and-quality/SKILL.md
- https://github.com/jeremylongshore/claude-code-plugins-plus-skills

pilotでは、`docs/ai/role-routing-index.md` が指す現行Implementer / Reviewer / Tester手順と、本メモの受入条件・参照範囲を暫定Role Skillとして使う。外部Skillのinstallやコピーは行わない。

## 手動読込順序と成果物

### implementer2

1. `docs/ai/core.md`
2. `docs/ai/role-routing-index.md` のimplementer2行とtrio routing
3. 本メモのContext / Policy参照のうち、現行role、旧core §4・§6–7、既存requirements/final
4. Coordinatorの依頼と本メモの受入条件
5. `git status` と対象3ファイルの現在差分

実装後は `docs/ai/reviews/radius_healthcheck/2026-07-21_016_implement.md` に変更、自己検証、未検証事項、読込プロセスの所感を記録してtechlead2へ返す。

### reviewer2

1. `docs/ai/core.md`
2. `docs/ai/role-routing-index.md` のreviewer2行とtrio routing
3. 本メモのContext / Policy参照のうち、現行role、旧core §6–7・§18.1、既存requirements/final
4. Coordinatorの依頼、本メモ、implement成果物、現在diff

`docs/ai/reviews/radius_healthcheck/2026-07-21_017_review.md` に重大度付き指摘、判定、読込プロセスの所感を記録してtechlead2へ返す。原則としてコードは編集しない。

### tester2

1. `docs/ai/core.md`
2. `docs/ai/role-routing-index.md` のtester2行とtrio routing
3. 本メモのContext / Policy参照のうち、playbook marker、現行role、旧core §18.1・§18.4–18.5
4. Coordinatorの依頼、本メモ、implement / review成果物、現在diff

まず `docs/ai/reviews/radius_healthcheck/2026-07-21_018_test_plan.md` に安全分類、静的・ローカル・実ホスト検証の境界を記録する。承認不要なread-only範囲で実施し、結果を `2026-07-21_019_test_result.md` に記録してtechlead2へ返す。実ホスト実行を当然視せず、必要性と副作用を再評価する。

## pilotで観察すること

各Roleは成果物に次を短く記録する。

- 指定外のContextを読んだか。読んだ場合は理由。
- 必要な情報が不足したか。
- Tech Leadの指定が多すぎたか、少なすぎたか。
- 他Roleと責務が重複したか。
- 公開Skill不採用が妥当だったか。
- Incident / Lesson / DecisionとしてKnowledgeへ残すべき内容が生じたか。
