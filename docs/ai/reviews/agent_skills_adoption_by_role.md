# 役割別 採用Skill項目（実装着手用）

作成日: 2026-07-23
参照元: skill_survey.md（全項目の評価ログ）

このファイルは `skill_survey.md` から「採用（参考にする）」判定の項目のみを抜き出し、
CCがSkill化に着手できるよう、取り込む実体と出典を明記したもの。
自作確定・現行優位・取り込まない項目は含めない（詳細はskill_survey.md参照）。

**出典検証(2026-07-23、Coordinator実施)**: 全9項目のうち`anthropics/knowledge-work-plugins`を出典とする7項目をWebFetchで実在・内容確認した。architecture(#3)・risk-assessment(#4)・code-review(#6)・tech-debt(#7)・testing-strategy(#9)はskill名・パス・内容とも記載通りで訂正不要。Requirements analysis(#1)は`feature-spec`が実在せず`write-spec`が正しいskill名だったため訂正した。Goal tracking(#2)は`roadmap-management`が実在せず`roadmap-update`が正しいskill名で、かつ「Decision Memos」の記述はroadmap-update内になく、同プラグインの`stakeholder-update`skillが正しい出典だったため訂正した。Implementer(#5)・Security review(#8、自作)は元々`anthropics/knowledge-work-plugins`を出典としていないため対象外。

**実行コード・権限の確認(2026-07-23)**: GitHub APIで`anthropics/knowledge-work-plugins`の`engineering/skills/`・`operations/skills/`・`product-management/skills/`配下を再帰的に確認したところ、blob(ファイル)は27件全てMarkdownで、shell/Python等の実行コードは0件だった。ファイル・ネットワーク・秘密情報へのアクセスを伴うコードはなく、TODO4-2の「実行コード」「権限」評価項目はいずれもリスクなしと判定できる。ライセンスはApache-2.0、446 commitsで活発に保守されている。

**未解決**: 参照元`skill_survey.md`(不採用・保留項目を含む全評価ログ)はこのリポジトリに保存されていない。TODO4-2の完了条件(採用・部分採用・不採用の理由を記録する)を満たすには、このファイルの復元または再作成が必要。

---

## Coordinator

### 1. Requirements analysis

**出典:** `anthropics/knowledge-work-plugins` の `write-spec` スキル(2026-07-23 Coordinator訂正: 壁打ち時点の記載`feature-spec`は実在しない。product-managementプラグインのskills一覧を実機確認し、`write-spec`が正しいskill名と判明)
- 正本: https://github.com/anthropics/knowledge-work-plugins/blob/main/product-management/skills/write-spec/SKILL.md
- 検証: 2026-07-23、WebFetchで実在・内容一致を確認済み(8セクション構成、MoSCoW、Given/When/Thenいずれも記載通り)

**取り込む実体:**
- PRDを8セクションで構成する型: 問題定義 / ゴール / **非ゴール** / ユーザーストーリー / 要件（P0/P1/P2） / 成功指標 / オープンクエスチョン / タイムライン考慮
  - 「非ゴール」は現行core.mdの「初回実装で含める範囲／除外する範囲」と概念一致。名称をPRD標準に揃える程度の変更で済む
- MoSCoW優先順位付け（Must/Should/Could/Won't）
- 受入条件をGiven/When/Then形式で書く型（現行requirement.mdの「確認項目」を置き換え、Testerのtest strategyと接続しやすくする）
- 優先度の規律: 「全部がP0なら、P0は存在しないのと同じ。すべてのmust-haveを疑え」

**適用先:** `requirement.md` のテンプレート構造

---

### 2. Goal tracking

**出典:** `anthropics/knowledge-work-plugins` の `roadmap-update` スキル(2026-07-23 Coordinator訂正: 壁打ち時点の記載`roadmap-management`は実在しない。正しいskill名は`roadmap-update`)
- 正本: https://github.com/anthropics/knowledge-work-plugins/blob/main/product-management/skills/roadmap-update/SKILL.md
- 検証: 2026-07-23、WebFetchで実在・内容一致を確認済み(RICE/MoSCoW/ICE、Now/Next/Laterいずれも記載通り)

**Decision Memosの出典訂正(2026-07-23)**: `roadmap-update`内にDecision Memosの記述は無かった(WebFetchで不在を確認)。実際の出典は同じproduct-managementプラグインの`stakeholder-update`スキル内「Decision Documentation (ADRs)」節。
- 正本: https://github.com/anthropics/knowledge-work-plugins/blob/main/product-management/skills/stakeholder-update/SKILL.md
- 構造: `Status` / `Context` / `Decision` / `Consequences`(positive/negative) / `Alternatives Considered`。Tech Leadの`architecture`スキルのADR(Options評価テーブル・Trade-off Analysis・Action Itemsを含む重量級)とは別物で、こちらは戦略判断向けの軽量版

**取り込む実体:**
- RICE / MoSCoW / ICE の優先順位付けフレームワーク（`roadmap-update`）
- Now / Next / Later の3分類構造（`roadmap-update`。既存core.mdの「on the horizon」セクションと相性が良い）
- Decision Memos（選択肢・根拠・トレードオフ・推奨をまとめる型、`stakeholder-update`の「Decision Documentation」が出典）。Tech Leadの「Architecture analysis」で採用するADR形式と見た目は似るが、**統合しない**（2026-07-23確定）。Decision Memoは優先順位づけ（What/When、よしのぶへの提言止まり）、ADRは実装方法選択（How、スコープ確定後）で権限が異なるため

**適用先:** 構想中の `iac_coverage.md`（IaC化されてない領域の棚卸し・優先順位付け）

---

## Tech Lead

### 3. Architecture analysis

**出典:** `anthropics/knowledge-work-plugins` の `architecture` スキル
- 正本: https://github.com/anthropics/knowledge-work-plugins/blob/main/engineering/skills/architecture/SKILL.md
- ミラー: https://skillsmp.com/skills/anthropics-knowledge-work-plugins-engineering-skills-architecture-skill-md

**取り込む実体:**
- ADR（Architecture Decision Record）の型:
  ```
  # ADR-[number]: [Title]
  **Status:** Proposed | Accepted | ...
  [選択肢・トレードオフ・結論]
  ```
- 用途例: Molecule採用可否、Codex/CC固定化の判断など、技術選択の軽量な意思決定記録

**適用先:** 新設予定の `docs/ai/adr/`（Coordinatorの Decision Memoとは統合せず別Skillとして運用。権限の違い（How vs What/When）を理由に2026-07-23確定）

---

### 4. Risk analysis

**出典:** `anthropics/knowledge-work-plugins` の `risk-assessment` スキル（Operationsプラグイン）
- 正本: https://github.com/anthropics/knowledge-work-plugins/blob/main/operations/skills/risk-assessment/SKILL.md
- ミラー: https://explainx.ai/skills/anthropics/knowledge-work-plugins/risk-assessment

**取り込む実体:**
- リスクカテゴリ分類: Operational（プロセス障害・システム障害）/ Financial / Compliance / Strategic / Reputational / Security
  - homelab文脈に翻訳: Operational=システム障害・停電、Security=認証情報露出・不正アクセス等
- レジスタ形式:
  ```
  | Risk | Likelihood | Impact | Mitigation |
  ```
- 注記: Legal版（`legal-risk-assessment`）は金銭的％表記で契約リスク向けのため不採用。Operations版を採用

**適用先:** requirement.md作成時のリスク欄、または個別のADR内

---

## Implementer

### 5. Ansible implementation（内部で使う個別言語の公式スタイルガイド）

**方針:** Ansible専用の公式Skillは存在しない。Ansible内部で使う個別言語（Shell / Python / Jinja2）ごとに、ベンダー公式の一次情報を直接参照する。SKILL.md形式の非公式ラッパー（例: testdino-hq/google-styleguides-skills）は導入しない。

**出典（Shell）:** Google Shell Style Guide
- https://google.github.io/styleguide/shellguide.html

**取り込む実体:**
- shellは小規模ユーティリティ・単純なラッパースクリプトに限定して使う
- 100行を超える、または制御フローが複雑になった場合は構造化言語（Python）へ書き直す判断基準
- 現行core.mdの「shell責務は収集とJSON整形のみ」を補強する根拠として使う

**出典（Python）:** Google Python Style Guide
- https://google.github.io/styleguide/pyguide.html

**取り込む実体:**
- filter_plugin等のPythonコードにおける命名規則・例外設計等の基準

**出典（Jinja2/変数）:** Ansible公式ドキュメント
- 変数とJinja2: https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_variables.html
- テンプレーティング: https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_templating.html

**取り込む実体:**
- `{{ foo }}` で始まる値は行全体をクォートしないとYAMLパースエラーになる、という構文規則
- Jinja2ループ・条件はplaybook内では使えずtemplate内でのみ使う、という制約

**適用先:** `references/` に一次情報URLとしてリンクし、SKILL.md本体には要点のみ記載（原文の転記はしない）

---

## Reviewer

### 6. Code review（出力フォーマットのみ）

**出典:** `anthropics/knowledge-work-plugins` の `code-review` スキル
- 正本: https://github.com/anthropics/knowledge-work-plugins/blob/main/engineering/skills/code-review/SKILL.md
- ミラー: https://mcpservers.org/agent-skills/anthropic/code-review

**取り込む実体（フォーマットのみ。運用ロジックはcore.md §15が優位のため据え置き）:**
```
## Code Review: [PR title or file]
### Summary
### Critical Issues
| # | File | Line | Issue | Severity |
### Suggestions
| # | File | Line | Suggestion | Category |
### What Looks Good
### Verdict [Approve / Request Changes / Needs Discussion]
```

**適用先:** `review.md` の出力書式

---

### 7. Duplication / reuse check（分類のみ。運用手順は自作）

**出典:** `anthropics/knowledge-work-plugins` の `tech-debt` スキル
- 正本: https://github.com/anthropics/knowledge-work-plugins/blob/main/engineering/skills/tech-debt/SKILL.md

**取り込む実体:**
- 「Code debt」カテゴリの定義: Duplicated logic, poor abstractions, magic numbers → Bugs, slow development

**自作する運用手順（出典なし、2026-07-23決定）:**
- 発見・指示はTech Leadが担う（タスク分解時に既存filter_plugin/role/他playbookとの重複可能性を洗い出し、再利用対象をrequirement/タスク分解に明記）
- Reviewerは「指定された資産を実際に使ったか」を照合するだけの軽量な検査に限定する（全リポジトリ横断検索はさせない）

**適用先:** review.mdのチェック項目に1行追加

---

### 8. Security review（自作。Ansible公式ドキュメントが根拠）

**方針:** knowledge-work-pluginsの`code-review`が扱うのはWebアプリ向け（SQLi/XSS/CSRF）で、Ansible特有の攻撃面（shell/commandモジュールへの変数注入）はカバーしない。ただし、Ansible公式ドキュメントに直接的な根拠がある。

**出典:** Ansible公式モジュールドキュメント
- shellモジュール: https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/shell_module.html
- commandモジュール: https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/command_module.html

**取り込む実体:**
- shellモジュールでテンプレート化された変数を使う場合は、必ず`quote`フィルタを使ってインジェクションを防ぐ（公式ドキュメントの例で明記）
- commandモジュールはシェルを介さないため、可能な限りshellよりcommandを優先する（クォーティングミスによる意図しないコマンド実行を防げるため公式に推奨）
- `argv`パラメータ（リスト形式）を使うと、文字列結合よりさらに安全

**その他、自作で追加すべき観点（公式ドキュメントに直接の記載なし。recovery pipelineのインシデント実例が根拠）:**
- `no_log`の付け忘れによる機密変数のログ露出
- `delegate_to`と信頼できない変数の組み合わせ
- `lookup()`プラグイン経由での信頼境界超え

**適用先:** Reviewer専用のreferences/として自作し、code-reviewの構造に差し込む

---

## Tester

### 9. Test strategy

**出典:** `anthropics/knowledge-work-plugins` の `testing-strategy` スキル
- 正本: https://github.com/anthropics/knowledge-work-plugins/blob/main/engineering/skills/testing-strategy/SKILL.md

**取り込む実体:**
- unit / integration / e2e のカバレッジ配分とtest plan作成の型
- 注意: 境界値分析・property-based testingは含まれない（別途自作）

**自作が必要な翻訳作業:**
- 「e2e」相当をAnsible文脈に翻訳する（dry-run → apply → 事後健全性チェックの3段階、といった対応関係を定義する）

**適用先:** `test_plan.md` のテンプレート構造

---

## 共通事項（複数役割にまたがる論点）

1. **ADR（Tech Lead）とDecision Memos（Coordinator）は統合しない（2026-07-23確定）**
   見た目の型（選択肢・根拠・トレードオフ・推奨）は似ているが、扱う判断の権限が異なる。
   - Decision Memo（Coordinator）: タスクの優先順位づけ（What/When）を判断できる。「今やる価値があるか」はよしのぶへの**提言**に留まり、決定権を持たない
   - ADR（Tech Lead）: スコープが確定した後の実装方法選択（How）を判断する
   Coordinatorが実装方法に口を出す、Tech Leadが優先順位を決める、のどちらも想定しない。別々のSkillのまま残す。

2. **公式一次情報の扱い方**
   Google Style Guide・Ansible公式ドキュメントは、SKILL.md本体に転記せず `references/` からURL参照する形にする（コピーライト・保守性の両面から）。

3. **表現方法・書き方レベルの指摘は対象外**
   上記スタイルガイドはImplementerが実装時に自己適用するツールに限定する。Reviewer/Testerの検査基準には拡張しない（2026-07-23、よしのぶ確認済み）。
