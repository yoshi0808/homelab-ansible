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

| 情報 | Coordinator | Tech Lead | Implementer | Reviewer | Tester |
|---|---|---|---|---|---|
| `docs/ai/core.md` | 起動時 | 起動時 | 起動時 | 起動時 | 起動時 |
| `docs/ai/role-routing-index.md` | 起動時 | 起動時 | 起動時 | 起動時 | 起動時 |
| `docs/ai/context/system/overview.md` | 着手時 | 着手時 | 必要時 | 必要時 | 必要時 |
| 対象領域System Context(`proxmox.md`/`radius.md`/`monitoring.md`/`semaphore.md`、該当するもののみ) | 必要時 | 着手時(詳細) | 着手時(詳細) | 着手時(詳細) | 着手時(詳細) |
| `docs/ai/context/ansible/repository-overview.md` | 必要時 | 着手時 | 必要時 | 必要時 | 必要時 |
| `docs/ai/context/ansible/inventory-map.md` | 必要時 | 着手時(対象host/group特定) | 着手時(対象特定に必須) | 必要時 | 着手時(対象特定に必須) |
| `docs/ai/context/ansible/playbook-map.md` | 必要時 | 着手時(対象playbook・種別・Policy候補の特定に必須) | 着手時(対象行) | 着手時(対象行) | 着手時(対象行) |
| `docs/ai/context/ansible/role-map.md` | 必要時 | 必要時(概要はplaybook-mapで足りる) | 着手時(実装対象roleの入出力確認に必須) | 着手時(対象role) | 着手時(対象role) |
| Policy(`docs/ai/policies/`、対象分野のみ) | 必要時 | 着手時(該当分野) | 着手時(該当分野) | 着手時(該当分野) | 着手時(該当分野) |
| Issue / 受入条件(案件の依頼文) | 起動時点で自分が起点 | 着手時(必須) | 着手時(必須) | 着手時(必須) | 着手時(必須) |
| PR / diff | 必要時(Tech Leadの統合報告で足りることが多い) | 必要時 | 自分の実装(常時) | 着手時(必須、レビュー対象そのもの) | 着手時(必須、検証対象そのもの) |
| Knowledge(`docs/ai/memory/`、Claude Memoryを含む) | 起動時(重要Decisionは常に前提とする) | 必要時(重要Decision) | 必要時(対象関連) | 必要時(対象関連) | 必要時(対象関連) |
| 委任Skill(Tier判定、`skills/delegation-tier/SKILL.md`) | 案件ごとに毎回参照(Tier判定はCoordinatorが確定する) | 着手時(受領した案件がTier 3以上であることの確認) | 不要 | 不要 | 不要 |
| 規範文書レビュー(`skills/document-norm-review/SKILL.md`) | 必要時(自ら規範を書き換えるとき) | 必要時(規範の再配置を伴う分解のとき) | 不要 | **着手時(レビュー対象が規範文書を含む場合は必須)** | 不要 |

## 判断の原則(計画書からの引き継ぎ、変更なし)

- Tech Leadは全体像を理解し、必要Contextを選ぶ。Tech LeadのContext指定に不足があれば、各Roleは追加調査する。
- Implementerは対象機能と接続部分を深く理解する。
- Reviewerは要件・差分・影響する構成を理解する。
- Testerは対象構成・依存関係・期待状態・安全な検証範囲を理解する。
- 「必要時」は禁止ではなく既定で省略してよいという意味。実際に迷いが生じたら読むことをためらわない。

## Coordinatorの扱い(2026-07-22、pilot2/3レビューの指摘を反映)

pilot3のTODO2-2レビューで「Role別Contextマトリクスにタイミング軸とCoordinatorの明示的な扱いが欠けている」との指摘があり、この節で解消する。Coordinatorは実装Contextの大半を「必要時」に留め、Tech Leadへの委任時に対象System/Ansible Contextの選定を委ねる。ただしIssue受理・Knowledge(重要Decision)・委任Skill(Tier判定)の3つは常時参照する。これはCoordinatorがコンテキスト量を抑えつつ、委任判断とTier判定の質を保つための線引きである。

## 完了条件の確認

- 各Roleについて「なぜこの情報が必要か」「なぜ他の情報は不要か」を、上表の列とタイミング区分で説明できる。
- 新しい情報を追加するとき、この表に1行追加するだけで済む。

## 未解決・持ち越し事項

- `docs/ai/context/ansible/playbook-map.md`が記録した「`prometheus_update_check`と`ubuntu_vm_patch_policy.md`§3.4の不一致」は、Policy自体の見直しが必要なfollow-up候補として残る(TODO2-4の対象外)。
- Policy本体(`docs/ai/policies/`配下)はTODO2-1の推奨構成にディレクトリが挙がっているが、個別Policyファイルの本実装はPhase2の本設計(TODO2-1完了確認)後に着手する。
