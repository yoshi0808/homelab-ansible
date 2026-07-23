# Skill探索 棚卸し表

作成日: 2026-07-23
版: v1.0（継続更新）

対象: homelab-ansible の AI運用体制（Coordinator / Tech Lead / Implementer / Reviewer / Tester）に
Agent Skillsをどう導入するかの調査記録。

参照:
- docs/ai/prompts/core.md（現行のAI運用フロー・レビュー観点）
- Claude chat「Ansible playbook5」「Ansible Playbook3」等（Skill探索の壁打ち経緯）

---

## 前提・方針

- **公式ベンダー提供のみを取り込み対象とする**（個人製作物は原則対象外）
- 探索対象は3層:
  1. `anthropics/skills` — ドキュメント処理系の実務ツール（docx/pdf/pptx等）→ **今回の目的とマッチしない**
  2. `anthropics/knowledge-work-plugins` — 役割・工程ベースの汎用ナレッジワークSkill（85+スキル、15プラグイン）→ **本命。レビュー中**
  3. ベンダー固有（Red Hat Agentic Skills等）— Ansible/RHEL/AAP寄りだが実例が薄く、そのままの取り込みは困難 → **参考程度**
- Ansible / Proxmox / homelab固有の項目は、公式Skillが存在しないことが判明しても正常（自作前提）
- 判定は3種類:
  - **取り込む** — 該当Skillをそのまま/軽微修正で導入
  - **参考にする** — 構成・書き方の型だけ借りて自作
  - **取り込まない** — 該当なし、または自作確定（IaC固有・homelab固有）

---

## 棚卸し表

| Role | 探すSkillカテゴリ | 目的 | 対応候補（knowledge-work-plugins） | 暫定所見 | 評価結果 | 備考 |
|---|---|---|---|---|---|---|
| Coordinator | Requirements analysis | 要求整理 | **feature-spec**（Product Management） | PRD8セクション構造（問題定義・ゴール・非ゴール・ユーザーストーリー・要件P0/P1/P2・成功指標・オープンクエスチョン・タイムライン）。非ゴールは既存core.mdの「初回実装で含める/除外する範囲」と概念一致。Given/When/Then受入条件形式、「全部P0ならP0は無いのと同じ」という優先度規律が新規収穫 | **参考にする** | Given/When/Then形式を受入条件に採用するとTester「Test strategy」との接続が向上 |
| Coordinator | Goal tracking | 進捗管理 | **roadmap-management**（Product Management） | RICE/MoSCoW/ICEでNow/Next/Laterのロードマップ管理 | **参考にする** | iac_coverage.md構想の優先順位付けに直接使える |
| Coordinator | Traceability | 受入条件の明確化 | 該当なし | 規制産業QA手法（requirements traceability matrix）。feature-specにも明示的なrequirement-ID紐付け機構は無く、85スキル中に該当なしで最終確定 | **取り込まない（自作確定）** | |
| Tech Lead | Architecture analysis | Context・Policy選択 | **architecture**（Engineering） | 技術選定をADR（Architecture Decision Record）として文書化する形式。`# ADR-[number]: [Title]` + Status + 選択肢・トレードオフ・結論。Molecule採用可否やCodex/CC固定化のような技術選択の軽量意思決定記録として使える。roadmap-management（PM）の「Decision Memos」と見た目は似るが、**統合しない**（2026-07-23確定：Decision Memoは優先順位づけ＝What/When＝提言止まり、ADRは実装方法選択＝How＝スコープ確定後、で権限が異なるため） | **参考にする** | `docs/ai/adr/`のような置き場を新設し、requirement/implementとは別の粒度で運用する案 |
| Tech Lead | Risk analysis | リスク分析 | **risk-assessment**（Operations） | Operational/Financial/Compliance/Strategic/Reputational/Securityの6カテゴリでリスクを識別し、Likelihood×Impact×Mitigationの表形式でレジスタ化。「system outages」がOperationalに含まれておりhomelab文脈に近い。Legal版（legal-risk-assessment、金銭的%表記）より転用しやすい | **参考にする** | カテゴリ名をhomelab文脈（Operational=システム障害、Security=認証情報露出等）に翻訳して採用 |
| Tech Lead | Task decomposition | 実装可能単位への分解 | sprint-planning（Product Management、参考程度） | ソフトウェアチームのアジャイル文脈（epicをsprintタスクに分解）向けで、homelabのソロ運用とは前提が異なる。core.mdの既存requirement仕様パターン（目的・対象・確認項目・制約・初回除外範囲）の方がすでに体系化されており優位 | **取り込まない（現行が優位）** | |
| Tech Lead | Codebase exploration | 着手前のコード探索 | 該当なし | Anthropicのmulti-agent research手法（explore段階）が最も近い型。**タスク分解時に既存filter_plugin/role/他playbookの重複可能性を洗い出し、再利用対象をrequirement/タスク分解に明記する責務を持つ**（Reviewerの重複検査を軽量化するための事前作業） | **取り込まない（自作、役割定義済み）** | Reviewerの「Duplication / reuse check」と対になる設計（2026-07-23決定） |
| Implementer | Ansible implementation | 正しい実装 | 該当なし（Ansible専用skillは無いが、内部で使う個別言語の公式スタイルガイドは存在） | Google Shell Style Guide（google.github.io/styleguide）、Google Python Style Guide（同）は公式。shellは小規模ユーティリティに限定・100行/複雑な制御フローで構造化言語へ移行、という基準はcore.mdの「shell責務は収集とJSON整形のみ」を補強できる。SKILL.md形式のラッパー（testdino-hq/google-styleguides-skills等）は非公式なので導入対象外、一次情報のみ参照 | **参考にする（一次情報を自作SKILL.mdのreferences/から引用）** | Jinja2はdocs.ansible.comのBest Practices（Ansible公式）を同様に参照。正規表現は該当する公式スタイルガイド見当たらず |
| Implementer | Facts verification | 既存の正しい値の再利用 | 該当なし | 同上。公式skillなし | **取り込まない（自作確定）** | `ansible.builtin.setup`との照合手順をAnsible公式ドキュメント参照で自作 |
| Implementer | Idempotency | 冪等性 | 該当なし | 同上。公式skillなし | **取り込まない（自作確定）** | `--check`二重実行等、core.mdの既存運用がベース |
| Implementer | Repository exploration | 既存資産の活用 | 該当なし | Tech Leadの「Codebase exploration」（発見・指示）に対して、実装時に指定資産を実際に見つけて使う「実行フェーズ」の作業。重複ではなく上流/下流の関係と確定（2026-07-23） | **取り込まない（実行時対応として位置付け）** | Tech Leadの項と対で運用。単独のSkillとしては不要 |
| Implementer | Molecule workflow | 境界値fixture・localhost harness | 該当なし | Ansible公式テストツール。knowledge-work-pluginsには無い | **取り込まない（自作確定）** | Testerの同項目と共有スキル化 |
| Reviewer | Code review | 差分評価 | **code-review**（Engineering） | セキュリティ・パフォーマンス・正確性・保守性の4軸。出力テーブル形式（File/Line/Issue/Severity、Critical Issues/Suggestions 2階層）は採用。severity運用ロジックそのものはcore.md §15の5分類の方が精緻 | **参考にする（表形式のみ採用）** | review.mdの出力書式に流用 |
| Reviewer | Security review | セキュリティ評価 | code-review内包（SQLi/XSS/CSRF/認証/認証情報露出） | Ansibleの実際の懸念（shell/commandモジュールへの変数注入、Jinja2テンプレートインジェクション、no_log漏れ、delegate_to悪用）はカバー範囲外。攻撃面が根本的に異なる | **取り込まない（自作）** | 独自referenceとして自作し、code-reviewの構造に差し込む形が現実的。recovery pipelineの引数検証バグ実例が叩き台になる |
| Reviewer | Drift detection | 影響範囲の評価 | 該当なし | IaC固有（weekly git baseline比較）。85スキル中に無い | **取り込まない（自作）** | |
| Reviewer | Scope management | 設計との整合性評価 | 該当なし | code-reviewの出力はCritical Issues/Suggestionsの2階層のみ。「スコープ外」の分類や棄却理由の監査証跡運用は存在しない。core.md §15（must-fix/suggestion/nit/的外れ/スコープ外の5分類＋トリアージ運用）の方が明確に精緻 | **取り込まない（現行が優位）** | 出力テーブル形式（File/Line/Issue/Severity）はreview.mdの書式として部分的に参考にできる |
| Reviewer | Duplication / reuse check（新規追加） | 共通ロジックの重複防止 | **tech-debt**（Engineering）のCode debt分類（Duplicated logic, poor abstractions） | 発見・指示はTech Leadの「Codebase exploration」が担う（タスク分解時に再利用対象を指定）。Reviewerの役割は「指定された資産を実際に使ったか」の照合に軽量化。全リポジトリ横断検索はReviewerに持たせない | **参考にする（分類の型を採用、運用ルールは自作）** | 2026-07-23: 当初Reviewerに横断検索を持たせる案だったが、負荷が重いためTech Leadの事前指定＋Reviewerの照合に再設計。TODO7-2の「OS command由来の指標を自前計算で代替」の再発防止に直結 |
| Tester | Test strategy | テスト設計 | **testing-strategy**（Engineering） | unit/integration/e2eのカバレッジ配分とtest plan作成の型。境界値・property-basedは含まれない | **参考にする** | e2e概念をAnsible文脈（dry-run/apply/健全性確認）に翻訳する作業が必要 |
| Tester | Boundary value analysis | 境界値fixture設計 | 該当なし | 古典的QA技法。85スキル中に無い | **取り込まない** | QA教科書（ISO/IEC/IEEE 29119等）を直接参照して自作 |
| Tester | Fixture design | localhost harness | 該当なし | Moleculeの守備範囲（delegated driver） | **取り込まない** | Molecule公式ドキュメント参照で自作。Implementerと共有スキル化 |
| Tester | Molecule | 境界値・harness | 該当なし | 同上 | **取り込まない** | Ansible公式ツール。Skill化自体をよしのぶ側で行う。Implementerと共有 |
| Tester | Property-based testing | 性質ベーステスト | 該当なし | Hypothesis等。85スキル中に無い | **取り込まない** | Hypothesis公式ドキュメント参照で自作 |

---

## 精読の進行順

Tester → Reviewer → Implementer → Tech Lead → Coordinator の順で評価を進める（後半ほど難易度高）。

- [x] `engineering/skills/testing-strategy/SKILL.md` — Tester（2026-07-23 評価済み。詳細は棚卸し表参照）
- [x] `engineering/skills/code-review/SKILL.md` — Reviewer（2026-07-23 評価済み。Security reviewは自作確定、Scope managementは現行core.mdの方が精緻と判明）
- [x] Implementer関連（2026-07-23 評価済み。Ansible専用skillは無いが、内部言語（Shell/Python）の公式スタイルガイド参照方式に転換。Molecule等は自作確定）
- [x] Tech Lead関連（2026-07-23 評価済み。architecture=ADR形式とrisk-assessment（Operations）を採用。system-designは今回未使用。Task decompositionは現行core.mdが優位）
- [x] Coordinator関連（2026-07-23 評価済み。feature-spec・roadmap-managementを採用。Traceabilityは自作最終確定）

**棚卸し完了（Tester→Reviewer→Implementer→Tech Lead→Coordinatorの全5役割）**

## 総括

全21項目（Duplication/reuse check含む）の内訳:

| 判定 | 件数 | 内訳 |
|---|---|---|
| 参考にする | 8 | Test strategy, Code review（表形式のみ）, Duplication check（分類のみ）, Ansible implementation（言語別公式ガイド）, Architecture analysis, Risk analysis, Requirements analysis, Goal tracking |
| 取り込まない（自作確定） | 10 | Boundary value analysis, Fixture design, Molecule（Tester/Implementer共有）, Property-based testing, Security review, Drift detection, Facts verification, Idempotency, Codebase exploration, Traceability |
| 取り込まない（現行が優位） | 2 | Scope management, Task decomposition |
| 実行時対応として位置付け（単独skill不要） | 1 | Repository exploration |

**Ansible/Proxmox/homelab固有の領域は、公式skillが一貫して存在しなかった**（Tester・Implementerで顕著）。一方で、Coordinator・Tech Lead・Reviewerの「工程・意思決定の型」は knowledge-work-plugins から相応に借りられた。

## 今後の進め方（skillsフォルダ配置までのTODO）

### 前提となる境界線の整理

core.mdの中身は3層に分かれる。**Skillと呼べるのは③だけ**。①②はcore.mdに残す（役割定義・ローカルルールは「一般人が馴染みのない専門知識」ではなく、このプロジェクト固有の運用取り決めのため）。

| 層 | 中身の例 | 置き場所 |
|---|---|---|
| ① 常時必要な絶対ルール | 誰が誰か、名前解決方針、IPアドレス直書き禁止、秘密情報の扱い、.gitignore方針 | core.md（コンパクト化後も残す） |
| ② 役割の責務・ハンドオフ手順 | Coordinator/TechLead/Implementer/Reviewer/Testerの分担、ファイル命名規則（YYYY-MM-DD_NNN_type.md）、agmsg受け渡し規約、トリアージ運用 | core.md（役割ごとに再編する余地はあるが、Skillではない） |
| ③ 専門技法（Skill本体） | ADR、PRD構造、リスクレジスタ、Given/When/Then、テスト戦略、境界値分析、Shell/Pythonスタイルガイド参照、Duplication check基準 | `skills/` |

knowledge-work-pluginsの構造もこれと一致する。`.claude-plugin/plugin.json`・`.mcp.json`（②相当）と`skills/`（③相当）は別ファイルに分離されている。同じ分離をhomelab-ansibleにも適用する。

### TODO（フェーズ順）

- [ ] **フェーズ1: core.mdの棚卸し** — 現行core.mdの全セクションを①②③に仕分ける。③に該当する箇所（Codexレビュー観点、トリアージ表の一部等）を抽出リストにする
- [ ] **フェーズ2: Skillインベントリの確定** — 本表の「参考にする」8件＋自作確定分のうち実際にSkill化するものを最終リストにする。粒度の上限を決める（役割ごとに増えすぎると発火競合が起きるため、1役割あたり3〜5本目安）
- [ ] **フェーズ3: SKILL.md執筆** — 各Skillについて
  - `name`・`description`（発火条件。ここが一番重要）
  - 本文（自作技法 or 公式ソースの要約）
  - 外部一次情報（Google Style Guide、docs.ansible.com等）は本文に埋め込まず`references/`から参照する形にする
- [ ] **フェーズ4: core.mdのスリム化** — ③として抽出した内容をcore.mdから削除し、③に該当するSkill名だけを索引として残す（「〇〇はskills/xxxを参照」の一覧）
- [ ] **フェーズ5: 配置構成の決定** — `.skills/`を正本にして、CC用（`.claude/skills`）・Codex用の両方にsymlinkする構成にする（エージェント間で知識を共有するため）
- [ ] **フェーズ6: ドッグフーディング** — 新設したSkill自体をCodex（reviewer）にレビューさせる（既存の実装レビューフローをそのまま適用）
- [ ] **フェーズ7: 試験運用** — 次の1playbookサイクルで実際に発火するか確認する。descriptionが緩すぎて誤発火する/厳しすぎて発火しない、のどちらもあり得るため実測が要る
- [ ] **フェーズ8: core.md索引の整備** — Coordinatorが「今どんなSkillが存在するか」を一覧できるよう、core.mdまたは別ファイルにSkill一覧表を置く

### 確定事項

- **役割の責務定義（②）はSkillにしない（2026-07-23確定）**。Skillは「発火条件（description）に応じて必要な時だけ読み込む専門知識」のための仕組みであり、「Reviewerとして常にどう振る舞うか」のような役割定義は常時有効な文脈が必要で、発火制御の仕組みとそもそも相性が悪い。役割定義はcore.md（またはCC/Codexの起動時プロンプト）に残す。

以上でSkillと役割定義の境界線に関する論点は解消。フェーズ1（core.mdの棚卸し）に着手可能な状態。

### 保留事項（2026-07-23、Yoshinobu確認: 抽象的に決め切れるものではなく、実プロジェクトで実際に使う場面が出てから判断する）

- Given/When/Then受入条件をrequirement.mdに導入する場合の書式変更
- `docs/ai/adr/`の新設要否とファイル命名規則
- Duplication / reuse checkの運用フロー具体化（Tech Leadの指定→Implementerの実行→Reviewerの照合を、requirement.md/implement.mdのどの欄に落とし込むか）
- tech-debtスキルの他の観点（Test debt, Documentation debt, Infrastructure debt分類）を1-2ヶ月全体レビューの棚卸し軸として使えないか

これら4件はフェーズ1〜8のTODOをブロックしない。該当する具体的な案件が発生した時点で、その案件のTech Lead/Coordinatorが必要性を判断して採用可否を決める。

## 解消済みの重複疑い

- ~~Tech Lead「Codebase exploration」 と Implementer「Repository exploration」~~ → **解消（2026-07-23）**。重複ではなく上流/下流の関係と確定。Tech Leadが実装前に既存資産を洗い出し再利用対象を指定（発見・指示）、Implementerが実装時にそれを実際に使う（実行）。Reviewerの「Duplication / reuse check」もこの流れの延長で軽量な照合ゲートとして再設計済み。
- Implementer「Molecule workflow」と Tester「Molecule」「Fixture design」— 未解消。共有スキル化の方針は維持。実装時に1本化する。

## 既知の注意点

- knowledge-work-pluginsの各SKILL.mdは `## Company Context [CUSTOMIZE]` のような欄を持ち、企業固有の用語・プロセスを書き込む前提で設計されている。core.mdの該当セクション（Codexレビュー観点、トリアージ表等）を、この構造に合わせて抜き出す作業になる見込み。
- 借用したSkillは、`.skills/`を正本にしてCC/Codex双方からsymlink参照する構成が望ましい（役割間・エージェント間で同じ知識を共有するため）。
- 「公式Skillだから優れている」とは限らない。Scope managementのように、現行core.mdの運用ルールの方が精緻な項目もある。比較して都度判断する。
- **設計判断（2026-07-23）**: 共通利用されるロジックの重複防止は、Tech Lead（タスク分解時に既存資産を探索し再利用対象を指定＝能動的発見）とReviewer（実装後に指定資産が実際に使われたか照合＝軽量な検査ゲート）の二段構え。Reviewerに全リポジトリ横断検索という重い仕事を持たせない設計。
- **探索方針の転換（2026-07-23）**: 「Ansible専用skill」を探しても無いのは確定的。代わりに、Ansible内部で使う個別言語（Shell/Python/Jinja2）ごとに公式スタイルガイドを引用する方式に切り替える。SKILL.md形式の非公式ラッパーではなく、ベンダー公式の一次情報（google.github.io/styleguide、docs.ansible.com等）を`references/`に直接参照する。
- **適用範囲の境界線（2026-07-23）**: 上記の言語別公式スタイルガイドは**Implementerが実装時に自己適用するツールに限定**する。Reviewer・Testerの検査基準（must-fix/nit判定やテスト設計の合否）には拡張しない。表現・書き方レベルの指摘をReviewer/Testerに許すと、実装者ごとの癖の違いがnitとして際限なく往復を生み、CC/Codex間の実装者切り替え運用と衝突する。スタイルは「実装時に一度適用して終わり」、レビュー・テストの土俵には乗せない。