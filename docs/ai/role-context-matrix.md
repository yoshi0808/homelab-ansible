# Role別Contextマトリクス

状態: **正本**。誰が・いつ・どの深さで・何を読むかを定義する。

## 読むタイミングの定義

| タイミング | 意味 |
|---|---|
| 起動時 | セッション開始時に必ず読む。案件を受ける前の前提。 |
| 着手時 | 案件を受けた直後、実装・レビュー・テストに入る前に読む。 |
| 必要時 | 着手時点では読まず、判断に迷った時・対象が広がった時だけ読む。 |
| 不要 | 通常この情報を読む必要はない。 |

## マトリクス

| 情報 | Coordinator | Implementer | Reviewer | Tester |
|---|---|---|---|---|
| `docs/ai/core.md` | 起動時 | 起動時 | 起動時 | 起動時 |
| `docs/ai/status.md`(現在地) | **起動時**(SessionStart hookが自動で載せる。更新責任もCoordinatorにある) | 不要 | 不要 | 不要 |
| `docs/ai/context/system/overview.md` | 着手時 | 必要時 | 必要時 | 必要時 |
| 対象領域のSystem Context(`docs/ai/context/system/`、該当するもののみ) | 着手時(詳細。Coordinatorが直接確認する) | 着手時(詳細) | 着手時(詳細) | 着手時(詳細) |
| 該当するOperations Context(`docs/ai/context/operations/`) | 着手時(該当するもの) | 着手時(該当するもの) | 着手時(該当するもの) | 着手時(該当するもの) |
| `docs/ai/context/ansible/repository-overview.md` | 着手時 | 必要時 | 必要時 | 必要時 |
| 対象inventory(`inventories/homelab/hosts.yml`等)・playbook・role本体(現物を直接参照) | 着手時(対象特定に必須) | 着手時(対象特定に必須) | 着手時(対象特定に必須) | 着手時(対象特定に必須) |
| **`docs/ai/policies/execution_boundary_policy.md`(実行境界)** | **起動時** | **起動時** | **起動時** | **起動時** |
| Policy(`docs/ai/policies/`、対象分野のみ。上記1本を除く) | 着手時(該当分野) | 着手時(該当分野) | 着手時(該当分野) | 着手時(該当分野) |
| Issue / 受入条件(案件の依頼文) | 起動時点で自分が起点 | 着手時(必須) | 着手時(必須) | 着手時(必須) |
| PR / diff | 必要時 | 自分の実装(常時) | 着手時(必須、レビュー対象そのもの) | 着手時(必須、検証対象そのもの) |
| Knowledge(`docs/ai/memory/`、Claude Memoryを含む) | 着手時(重要Decisionは常に前提とする) | **不要**(読まない) | **不要**(読まない) | **不要**(読まない) |
| 規範文書レビュー(`skills/document-norm-review/SKILL.md`) | 必要時(自ら規範を書き換えるとき) | 不要 | **着手時(レビュー対象が規範文書を含む場合は必須)** | 不要 |

**どのファイルが在るかは、ディレクトリそのものが正本である。この表へ一覧を持たない** — 一覧を持つと、Contextが増えたときに必ずドリフトする。各分類の定義は `docs/ai/context-classification.md`。

**この表はansy側の開発工程のRoleだけを扱う。** quory側の Operator は本番運用を支援する別の工程に属するため列を持たない(漏れではない)。読むものは `docs/ai/roles/operator.md`「読むもの」が定める。

## Auditorの参照範囲

上表はAuditor列を持たない。Auditorは技術Contextを一切読まないため、列を足すと大半が「不要」になり表が薄まるからである。Auditorは**案件クローズ時に1回だけ**起動し、読むのは次に限る。

| 情報 | タイミング |
|---|---|
| **案件フォルダ `docs/ai/reviews/<target>/` の全成果物** | 起動時(必須)。これが検査対象そのもの。**番号付き成果物**(各単位の `_implement.md` / `_review.md` / `_test_result.md`)を**互いに突き合わせる** — 書き手は各単位を実行した本人であり、**記録どうしの食い違いはそれ自体が指摘になる**。`progress.md` は必須成果物から撤廃した。過去の案件フォルダには残っているので、在れば読んでよい |
| `docs/ai/status.md`(現在地) | 起動時。行の記述内容が実態と一致しているか、新たな観測待ちの計上漏れがないかを見る。**該当行が残っていること自体は指摘にしない**(Auditorは消す前に呼ばれる設計のため)。除去はAuditorの合否通知を受けた**同じセッションのうちに**Coordinatorが行う(次回へ持ち越さない) |
| 成果物から**参照されている先** | 必要時。file:line・commitが実在し内容が一致するかの確認。**参照が無効になっていることを見つけるのが仕事の一部** |

**Coordinatorの説明は入力にしない。** 依頼文に書いてよいのは「どの案件か」「どこから読み始めるか」だけである。**「Coordinatorが説明しなければ分からないこと」は、記録の欠落として指摘されるべきもの**であり、説明で補ってはならない。

**System Context / Ansible Context / Policy / 実装Skillは読まない。** Auditorは技術的な正否を判定しないため、読んでも判断に使えず、読むこと自体が役割の越境になる。ただし**記録どうしの矛盾**は技術的な内容であっても指摘してよい(読解だけで判別できるため)。技術的な精査が要ると判断した場合は、追加のReviewer照合の起用をCoordinatorへ進言する(`docs/ai/roles/auditor.md`)。

## 判断の原則

- Coordinatorは全体像を理解し、必要Contextを選ぶ。Coordinatorのcontext指定に不足があれば、各Roleは追加調査する。
- Implementerは対象機能と接続部分を深く理解する。
- Reviewerは要件・差分・影響する構成を理解する。
- Testerは対象構成・依存関係・期待状態・安全な検証範囲を理解する。
- 「必要時」は禁止ではなく既定で省略してよいという意味。実際に迷いが生じたら読むことをためらわない。

## Coordinatorの扱い

**対象領域のSystem/Ansible Contextは「着手時」に、Coordinator自身が読む**(上表)。Issue受理とKnowledge(重要Decision)は変わらず常時参照する。

subagentは都度コールドスタートし、案件の依頼文で必要な文脈を受け取るため、進行中作業の一覧を読む必要がない(Knowledgeを読ませないのと同じ理由)。**subagentへ渡すべき状態は、Coordinatorが依頼文へ書く。**

**Knowledgeを読むのはCoordinatorだけである。** subagentはコールドスタートするため、どれが対象に関連するかを判断する材料を持たない。**各Roleが常に持つべき型は、Knowledgeを読ませるのではなく`docs/ai/roles/<role>.md`と`skills/`へ蒸留して渡す**(`docs/ai/memory-classification.md` 4節)。
