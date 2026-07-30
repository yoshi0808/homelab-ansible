# Role別Contextマトリクス

状態: **正本**。誰が・いつ・どの深さで・何を読むかを定義する。初版は`docs/ai/reviews/agent_skills_reorganization_plan.md` TODO2-4の成果物としてCoordinatorが統合・確定した(2026-07-22)。

## 読むタイミングの定義

| タイミング | 意味 |
|---|---|
| 起動時 | セッション開始時に必ず読む。READY報告の前提。 |
| 着手時 | 案件を受けた直後、実装・レビュー・テストに入る前に読む。 |
| 必要時 | 着手時点では読まず、判断に迷った時・対象が広がった時だけ読む。 |
| 不要 | 通常この情報を読む必要はない。 |

## マトリクス

| 情報 | Coordinator | Implementer | Reviewer | Tester |
|---|---|---|---|---|
| `docs/ai/core.md` | 起動時 | 起動時 | 起動時 | 起動時 |
| `docs/ai/role-routing-index.md` | 起動時 | 起動時 | 起動時 | 起動時 |
| `docs/ai/status.md`(現在地) | **起動時**(SessionStart hookが自動で載せる。更新責任もCoordinatorにある) | 不要 | 不要 | 不要 |
| `docs/ai/context/system/overview.md` | 着手時 | 必要時 | 必要時 | 必要時 |
| 対象領域System Context(`proxmox.md`/`radius.md`/`monitoring.md`/`semaphore.md`、該当するもののみ) | 着手時(詳細。2026-07-29、Tech Lead廃止に伴いCoordinatorが直接確認する) | 着手時(詳細) | 着手時(詳細) | 着手時(詳細) |
| `docs/ai/context/ansible/repository-overview.md` | 着手時 | 必要時 | 必要時 | 必要時 |
| 対象inventory(`inventories/homelab/hosts.yml`等)・playbook・role本体(2026-07-29、地図3ファイル廃止に伴い現物を直接参照) | 着手時(対象特定に必須) | 着手時(対象特定に必須) | 着手時(対象特定に必須) | 着手時(対象特定に必須) |
| Policy(`docs/ai/policies/`、対象分野のみ) | 着手時(該当分野) | 着手時(該当分野) | 着手時(該当分野) | 着手時(該当分野) |
| Issue / 受入条件(案件の依頼文) | 起動時点で自分が起点 | 着手時(必須) | 着手時(必須) | 着手時(必須) |
| PR / diff | 必要時 | 自分の実装(常時) | 着手時(必須、レビュー対象そのもの) | 着手時(必須、検証対象そのもの) |
| Knowledge(`docs/ai/memory/`、Claude Memoryを含む) | 起動時(重要Decisionは常に前提とする) | 必要時(対象関連) | 必要時(対象関連) | 必要時(対象関連) |
| 規範文書レビュー(`skills/document-norm-review/SKILL.md`) | 必要時(自ら規範を書き換えるとき) | 不要 | **着手時(レビュー対象が規範文書を含む場合は必須)** | 不要 |

## Auditorの参照範囲(2026-07-28新設。退役したPMOの節を置き換え)

上表はAuditor列を持たない。Auditorは技術Contextを一切読まないため、列を足すと大半が「不要」になり表が薄まるからである。Auditorは**案件クローズ時に1回だけ**起動し、読むのは次の4つに限る。

| 情報 | タイミング |
|---|---|
| **案件フォルダ `docs/ai/reviews/<target>/` の全成果物** | 起動時(必須)。これが検査対象そのもの。**番号付き成果物**(各単位の `_implement.md` / `_review.md` / `_test_result.md`)を**互いに突き合わせる** — 書き手は各単位を実行した本人であり、**記録どうしの食い違いはそれ自体が指摘になる**。`progress.md` は2026-07-29に必須成果物から撤廃した(`docs/ai/roles/coordinator.md`)。過去の案件フォルダには残っているので、在れば読んでよい |
| `docs/ai/status.md`(現在地) | 起動時。行の記述内容が実態と一致しているか、新たな観測待ちの計上漏れがないかを見る。**該当行が残っていること自体は指摘にしない**(Auditorは消す前に呼ばれる設計のため)。除去はAuditorの合否通知を受けた**同じセッションのうちに**Coordinatorが行う(次回へ持ち越さない) |
| 成果物から**参照されている先** | 必要時。file:line・commitが実在し内容が一致するかの確認。**参照が無効になっていることを見つけるのが仕事の一部** |

**Coordinatorの説明は入力にしない。** 依頼文に書いてよいのは「どの案件か」「どこから読み始めるか」だけである。**「Coordinatorが説明しなければ分からないこと」は、記録の欠落として指摘されるべきもの**であり、説明で補ってはならない。前身のPMO役はCoordinatorの自己申告を点検対象にした結果、最も重要な逸脱を検出できずに退役した(`docs/ai/reviews/process_retrospective/2026-07-28_003_pmo_retirement.md`)。

**System Context / Ansible Context / Policy / 実装Skillは読まない。** Auditorは技術的な正否を判定しないため、読んでも判断に使えず、読むこと自体が役割の越境になる。ただし**記録どうしの矛盾**は技術的な内容であっても指摘してよい(読解だけで判別できるため)。技術的な精査が要ると判断した場合は、追加のReviewer照合の起用をCoordinatorへ進言する(`docs/ai/roles/auditor.md`)。

## 判断の原則(計画書からの引き継ぎ、変更なし)

- Coordinatorは全体像を理解し、必要Contextを選ぶ(2026-07-29、Tech Lead廃止に伴いCoordinatorの直接責務へ統合)。Coordinatorのcontext指定に不足があれば、各Roleは追加調査する。
- Implementerは対象機能と接続部分を深く理解する。
- Reviewerは要件・差分・影響する構成を理解する。
- Testerは対象構成・依存関係・期待状態・安全な検証範囲を理解する。
- 「必要時」は禁止ではなく既定で省略してよいという意味。実際に迷いが生じたら読むことをためらわない。

## Coordinatorの扱い(2026-07-22、pilot2/3レビューの指摘を反映)

pilot3のTODO2-2レビューで「Role別Contextマトリクスにタイミング軸とCoordinatorの明示的な扱いが欠けている」との指摘があり、この節で解消する。**2026-07-29のTech Lead廃止以前は**、Coordinatorは実装Contextの大半を「必要時」に留め、Tech Leadへの委任時に対象System/Ansible Contextの選定を委ねていた。**Tech Lead廃止後は、詳細分解をCoordinator自身が行うため、対象領域のSystem/Ansible Contextを「着手時」に自ら読む**(上表。`docs/ai/reviews/process_retrospective/2026-07-29_005_techlead_retirement.md`)。Issue受理とKnowledge(重要Decision)は変わらず常時参照する。

2026-07-27に`docs/ai/status.md`(現在地)を追加した。subagentは都度コールドスタートし、案件の依頼文で必要な文脈を受け取るため、進行中作業の一覧を読む必要がない(Knowledgeを全件読ませないのと同じ理由)。**subagentへ渡すべき状態は、Coordinatorが依頼文へ書く。**

## 完了条件の確認

- 各Roleについて「なぜこの情報が必要か」「なぜ他の情報は不要か」を、上表の列とタイミング区分で説明できる。
- 新しい情報を追加するとき、この表に1行追加するだけで済む。

## 未解決・持ち越し事項

- Policy本体(`docs/ai/policies/`配下)はTODO2-1の推奨構成にディレクトリが挙がっているが、個別Policyファイルの本実装はPhase2の本設計(TODO2-1完了確認)後に着手する。
