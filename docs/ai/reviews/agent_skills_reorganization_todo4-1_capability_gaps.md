# TODO 4-1: Roleごとの能力不足(Skill探索の目的)

`docs/ai/reviews/agent_skills_reorganization_plan.md` TODO4-1の成果物。公開Skillを探す前に、各Roleに不足している能力を先に確定する。計画書の候補表(583〜608行)と、TODO7-2(pilot実測)・delegation skill草案(Phase4先行実証)の実績を統合してCoordinatorが作成した(2026-07-23)。

## 分類の考え方

各能力を次の3状態のいずれかに分類する。

- **確認済みギャップ**: pilotで実際に問題として現れ、`docs/ai/reviews/agent_skills_reorganization_todo7-2_result.md`に反映先まで記録済み。TODO4-2の公開Skill探索で最優先。
- **未検証の候補**: 計画書の初期候補表にあるが、pilotではまだ問題として顕在化していない。TODO4-2で探すが優先度は確認済みギャップより低い。
- **対応済み**: delegation skill草案(Phase4 TODO4-1/4-2の先行実証)で既に解消されたため、公開Skill探索は不要。

## Tech Lead

| 能力 | 状態 | 根拠 |
|---|---|---|
| 数値指標の意味論・入力source・丸め・境界を受入条件へ明記する手順 | 確認済みギャップ | TODO7-2: disk `used_percent`の意味論不足(pilot1で発覚、pilot2/3で再発防止確認) |
| 現行コードの責務分割を着手前に確認する手順 | 確認済みギャップ | TODO7-2: 原依頼の`tasks/main.yml`指定が実際は`tasks/check.yml`だった |
| 要件分解・タスク委任・工程の重さ判断(Tier分け) | 対応済み | delegation skill草案(Tier1-4)、Phase2 TODO2-2/2-3で実証(約20分/件) |
| repository exploration、architecture analysis | 未検証の候補 | 計画書初期候補。TODO2-2/2-3/2-4完了で相当程度は`docs/ai/context/`が代替済み、追加公開Skillの要否は要判断 |
| risk analysis | 未検証の候補 | 計画書初期候補。delegation skillのTier判定(安全境界の扱い)と一部重複 |

## Implementer

| 能力 | 状態 | 根拠 |
|---|---|---|
| OS commandが同じ指標を返す場合、自前計算前に意味論・境界を照合する検証手順 | 確認済みギャップ | TODO7-2: `round(used/total*100)`と`df` Use%の乖離(pilot1) |
| 閾値境界(境界直下・境界値・予約領域・丸め差)のfixtureを用意する手順 | 確認済みギャップ | TODO7-2: 同上、pilot2/3で受入条件明記により再発防止を確認済み |
| 新規lint違反と既存lint負債を分離する手順 | 確認済みギャップ | TODO7-2、依頼Bでも既存ansible-lint負債と新規差分の切り分けが課題化 |
| Ansible best practices、idempotency | 未検証の候補 | 計画書初期候補。pilot1-3では顕在化せず |
| secure implementation、Git workflow、minimal change | 未検証の候補 | 計画書初期候補。pilot1-3では顕在化せず |

## Reviewer

| 能力 | 状態 | 根拠 |
|---|---|---|
| marker(tester-gate等)を安全根拠に使う際、分類名だけでなく理由文・guard名・実行経路を照合する手順 | 確認済みギャップ | TODO7-2: `tester_mode`廃止済みだがmarker理由に残存(pilot1)。依頼Bで7 playbook全体に横展開・解消 |
| diff外の既存不整合をfollow-up Issueへ分離し、scope拡張しない手順 | 確認済みギャップ | TODO7-2、pilot2で類似のハンドオフ課題も観察 |
| code review、security review、change impact analysis | 未検証の候補 | 計画書初期候補。意味論バグ検出(pilot1)は既に強みとして実証済みのため優先度低 |
| severity classification | 未検証の候補 | 計画書初期候補。must-fix/suggestion/nit運用は既に機能している(3 pilot共通観察) |

## Tester

| 能力 | 状態 | 根拠 |
|---|---|---|
| Tester入力に原要求の監査参照(agmsg message ID等)を含める手順 | 確認済みギャップ | TODO7-2: Coordinator原依頼へ直接到達できずtraceabilityが弱い |
| source taskを副作用なしでfixture評価するlocalhost harness手順の一般化 | 確認済みギャップ | TODO7-2: pilot1で一時的に有効だったが標準手順化されていない |
| markerと実コードの副作用が異なる場合、実hostよりlocal証拠を優先する判断基準 | 確認済みギャップ | TODO7-2: marker driftの発見はlocal証拠優先の判断で可能だった |
| test planning、acceptance testing、failure-path testing | 未検証の候補 | 計画書初期候補。pilot1-3で既に強みとして実証済み(境界値・失敗系・独立検証) |
| idempotency testing、Ansible validation | 未検証の候補 | 計画書初期候補 |

## 共通(全Role横断)

| 能力 | 状態 | 根拠 |
|---|---|---|
| multi-agent collaboration(工程の重さ判断、重複調査の回避) | 対応済み | delegation skill草案。Anthropic公式ブログ"Building a multi-agent research system"を出典として採用済み |
| PR / diff workflow | 未検証の候補 | GitHub Issueは当面不使用のため計画書側で対象外と明記済み |
| memory / lessons management | 未検証の候補、Phase6と重複 | Phase6(Knowledge運用改善)が本題。TODO4-2で外部Skillを探す前にPhase6の設計を先に見るべき可能性がある |

## TODO4-2への申し送り(優先順位)

1. **最優先**: 確認済みギャップ(上記表で強調した10項目)に対応する公開Skillを探す。特にReviewer/Testerの「marker・理由文・実行経路の照合」「fixture設計」「監査traceability」は、Ansible/インフラ運用系のレビュー・テストSkillで類例がないか探す価値が高い。
2. **次点**: Tech Leadのrepository exploration/architecture analysisは、`docs/ai/context/`で相当程度自前実装済みのため、公開Skillは「補完」目的に限定して探す。
3. **後回し**: 「未検証の候補」全般は、pilotで問題化していないため今回のTODO4-2では深追いしない。Phase7以降の追加pilotで顕在化したら再検討する。
4. **対応済み(探索不要)**: Tech Leadのtask delegation/risk analysis、共通のmulti-agent collaborationはdelegation skill草案が既に対応している。重複購入(重複Skill導入)を避ける。

## 完了条件の確認

各Skill候補について、どのRoleのどの能力を改善するためかを上表で説明できる。特に確認済みギャップは全てTODO7-2の実例に紐づいており、根拠のない導入を避けられる。
