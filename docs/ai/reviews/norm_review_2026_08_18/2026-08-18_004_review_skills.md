# Norm Review: Skill層(`skills/*/SKILL.md`)定期照合 2026-08-18

## Summary

対象は `skills/` 配下14本すべての `SKILL.md`、および `ansible-correctness-review` / `test-gap-review` に付随する `agents/openai.yaml`(計16ファイル)。14本全文を読み、名指しする実体(パス・正本・コマンド)を自分で確認した。**High 1件**(`.claude/agents/reviewer.md`未更新により、Claude Code fallback経路のReviewerへ`ansible-correctness-review`/`test-gap-review`の併用を指示する経路が欠けている。着手時点では`.claude/skills/`のsymlinkも欠落していたが、レビュー作業中に2本とも出現した — 経緯は下記「未解決事項」参照)。**Medium 1件**(2本のSKILL.mdが「現行core.md」の引用として持つ文言が、現在のcore.mdに存在しない)。**Low 1件**(document-norm-reviewが`docs/ai/memory/`配下を根拠引用として本文に持つ)。Skill本文どうしの重複、退役概念(Tier制度・旧`tester_mode`・`role-map.md`等)への依存は検出しなかった。

## 確認した対象(14本 + 付随ファイル)

- `skills/ansible-correctness-review/SKILL.md`, `agents/openai.yaml`
- `skills/ansible-implementation-style/SKILL.md`
- `skills/ansible-security-review/SKILL.md`
- `skills/architecture-decision-record/SKILL.md`
- `skills/code-review/SKILL.md`
- `skills/document-norm-review/SKILL.md`
- `skills/duplication-reuse-check/SKILL.md`
- `skills/goal-tracking/SKILL.md`
- `skills/incident-recording/SKILL.md`
- `skills/requirements-analysis/SKILL.md`
- `skills/risk-assessment/SKILL.md`
- `skills/subagent-briefing/SKILL.md`
- `skills/test-gap-review/SKILL.md`, `agents/openai.yaml`
- `skills/test-strategy/SKILL.md`

あわせて `docs/ai/core.md`、`docs/ai/roles/reviewer.md`、`docs/ai/roles/coordinator.md`、`docs/ai/roles/implementer.md`、`docs/ai/roles/tester.md`、`docs/ai/roles/auditor.md`、`.claude/agents/reviewer.md`、`.claude/skills/`のsymlink一覧、`docs/ai/role-context-matrix.md`を突合先として確認した。

## Critical Issues

（該当なし。severityはHigh/Medium/Lowで報告する — `docs/ai/roles/reviewer.md`の重大度分類を準用し、本文の性質上「Critical」に届く実害〔本番影響〕ではないため区別した。)

## Findings

| # | File | Issue | Severity |
|---|---|---|---|
| 1 | `.claude/agents/reviewer.md` | `ansible-correctness-review`と`test-gap-review`は2026-08-10のcommit `860f635`で新設され、`docs/ai/roles/reviewer.md`は同commitで「Ansibleの計画または実装差分をレビューするときはAnsible correctness review… とtest gap review…を併用する」と必須化した。しかし`.claude/agents/reviewer.md`(Claude Code subagentとして起動するReviewerの実行機構、`git log`上の最終更新は2026-08-02のcommit — 2026-08-10より前)は、両Skillへの言及を一切持たない — `code-review`/`duplication-reuse-check`/`ansible-security-review`/`document-norm-review`の4本のみを列挙している(`stat`で現物のmtimeも2026-08-02、`cat`で内容も未更新を確認)。`docs/ai/roles/coordinator.md`は「codex側`reviewer`」を主、`.claude/agents/reviewer.md`によるClaude Code subagentを代替経路として残す設計であり(observed fact 2)、この代替経路が起動されたとき、agent定義の指示文には両Skillが現れない。着手時点(本レビュー開始時)では`.claude/skills/`のsymlinkも`ansible-correctness-review`/`test-gap-review`の2本が欠落しており(`ls .claude/skills/`で12本のみ実測)、Skillツールの一覧にも現れない状態だったが、レビュー作業中にこの2本のsymlinkが出現した(`git status --short`で`??`の未追跡ファイルとして検出、`stat`で生成時刻は本セッション中)。symlinkの出現経路は確認できていないため断定しないが、**symlinkの有無に関わらず`.claude/agents/reviewer.md`が両Skillの併用を指示していない事実は変わらない** — Skillツールの一覧に現れることと、そのSkillを使うようagent定義が指示することは別で、後者が欠けている。 | High |
| 2 | `skills/ansible-implementation-style/SKILL.md:18`、`skills/requirements-analysis/SKILL.md:16` | 前者は「現行core.mdの『shell責務は収集とJSON整形のみ』を補強する根拠として使う」、後者は「現行core.mdの『初回実装で含める範囲／除外する範囲』と同義」と、いずれも`docs/ai/core.md`からの引用として特定の文言を名指ししている。しかし現在の`docs/ai/core.md`をどちらの文言でも`grep`すると1件もヒットしない(確認済み)。core.mdでshellに触れるのは109行目「check系shellは観測に留め、判定・分類・通知・保存をshellへ持たせない」のみで、文言も概念の粒度も引用と異なる。両者の出典は`docs/ai/reviews/agent_skills_adoption_by_role.md`(Skill導入時の調査記録)で、これは当時のcore.mdを指していたと見られるが、2026-07-26の旧`core.md`退役・再構成でその文言自体が失われた後、Skill側の引用が追随していない。実害は小さい(Skill本体の指示自体は成立し続ける)が、「現行core.md」という現在形での名指しが事実と食い違っている。 | Medium |
| 3 | `skills/document-norm-review/SKILL.md` | 「欠陥クラス」各項目の「根拠:」に`docs/ai/memory/lessons/sweep-all-documents-stating-a-changed-boundary.md`および`docs/ai/memory/lessons/verification-referent-and-path-mismatch.md`への参照を持つ。`docs/ai/core.md`「開発の作業時に読む情報」6項は「Knowledge(`docs/ai/memory/`)を読むのはCoordinatorだけである。subagentは読まない」と定め、他のRole文書は2026-08-01〜08-02にlessonsへの参照を規範本体から除去する改訂を経ている。本Skillはこの掃引対象になっていない可能性がある。ただし引用は典拠の提示であり「参照先を読め」という指示ではないため、本Skillを読むReviewer(subagent)がこの参照を辿れず作業が破綻するわけではない。動作上のブロッカーではなく、規範文書の一貫性としての観測に留める。 | Low |

## 重複・退役概念の確認(指摘なし)

- Skill間の重複: `code-review`(出力フォーマット)へ`ansible-security-review`/`duplication-reuse-check`/`ansible-correctness-review`/`test-gap-review`/`document-norm-review`が「差し込む」形で積層しており、観点の重複は無い。`architecture-decision-record`と`goal-tracking`(Decision Memo)、`ansible-implementation-style`と`ansible-security-review`はそれぞれ「統合しない」「対象外」と明記され、境界も内容も競合しない。
- Tier制度: `skills/*/SKILL.md`のいずれにも`Tier`の記述なし(`grep -rn "Tier" skills/*/SKILL.md`でゼロヒット)。
- 退役した参照: `role-map.md`/`playbook-map.md`(`requirements-analysis`が「2026-07-29に廃止済み」と記す)はリポジトリ内に実在しないことを確認、記述と現物が一致。`iac_coverage.md`(`goal-tracking`)は「構想中」と明記されており未作成でも整合。
- Operator(observed fact 3)への言及: 14本のいずれも`Operator`を名指ししていない。Reviewer/Coordinator向けSkillが対象で、Operator固有の記述を持たないことは欠陥ではない。
- `.claude/agents/ansible-correctness-review/agents/openai.yaml`・`test-gap-review/agents/openai.yaml`: `interface.default_prompt`が`$ansible-correctness-review`/`$test-gap-review`という参照名を使っており、これはcodex側の起動名と一致すると見られる(agmsg経由codex Reviewerが主経路であるため、Skill新設時にこちらへは接続済み)。Finding 1はこの逆側、Claude Code fallback経路の接続漏れを指す。

## 未解決事項

- `.claude/skills/ansible-correctness-review`と`.claude/skills/test-gap-review`は本レビュー着手時に不在だったが、作業中(本セッション中)に`git status --short`上`??`の未追跡ファイルとして出現した。自分はこの2ファイルを作成していない。他agentの並行作業か、Claude Code harnessが `skills/` を検出して自動生成したものかは切り分けられていない。**未追跡のままGit管理下に無い**ため、`git add`はCoordinator判断。自分では削除・整形もしない(「他agentが並行して作る未追跡ファイルを自分の成果物として扱わない」に従う)。

## 未確認事項

- 各Skillが引用する外部URL(Ansible公式ドキュメント、Google Style Guide、`anthropics/knowledge-work-plugins`の各commit revision)は、ネットワーク到達性の検証手段を使わなかったため実在・内容一致とも未確認。パス表記の妥当性(GitHub上の実在パス)のみで判断できる範囲を超える。
- `docs/ai/role-context-matrix.md`は`ansible-correctness-review`/`test-gap-review`/`code-review`等の個別Skill名を持たず(Context読み込みタイミングの表であり対象が異なるため)、Finding 1との整合は矩形外として扱った。指摘はしていない。

## 指摘ゼロだったSkill

`architecture-decision-record` / `code-review` / `duplication-reuse-check` / `goal-tracking` / `incident-recording` / `risk-assessment` / `subagent-briefing` / `test-strategy` / `ansible-security-review` の9本は、参照先の実在・到達可能性・重複・退役概念のいずれにも指摘なし。

`ansible-correctness-review` / `test-gap-review` の2本は、**Skill本文が名指しする参照先(`docs/ai/roles/reviewer.md`、`docs/ai/policies/ansible_test_safety_policy.md`、`skills/ansible-implementation-style/SKILL.md`、`skills/ansible-security-review/SKILL.md`、`skills/code-review/SKILL.md`、`skills/test-strategy/SKILL.md`)はすべて実在し、内容面の指摘はゼロ**。ただしFinding 1(接続の断絶)の対象である。

## Verdict

Request Changes(High 1件、Medium 1件。是正の要否・書き方はCoordinator判断)
