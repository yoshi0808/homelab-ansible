# 安全境界を変えたら、その境界を述べている文書を全部掃引する

## 教訓

決定によって安全境界(誰が何を承認するか、何を禁止するか)が変わったとき、**その境界に言及している文書をすべて洗い出して同時に直す**。1箇所だけ直すと、残った文書が古い境界を主張し続け、それを読んだRoleが変更前の判断をする。

## 根拠(2026-07-26、承認権限のCoordinatorへの移管)

実ホスト操作の承認主体をYoshinobuからCoordinatorへ移す決定を行い、`docs/ai/roles/coordinator.md`に3分類を新設、`implementer.md` / `tester.md`にエスカレーション経路を追記、`.claude/settings.json`の`autoMode`に機械的な境界を宣言した。

しかし**`docs/ai/core.md`を直し忘れていた**。core.mdは全Roleが起動時に最初に読む共通原則の正本であり、そこには変更前のまま「運用上の採否、本番適用、**危険操作**、確定、commitはYoshinobuが判断する」と書かれていた。subagentがこれを読めば、本番影響のある操作はすべてYoshinobuへエスカレーションすべきだと解釈する。同じリポジトリ内で、最上位の文書と個別Role文書が別のことを言っている状態だった。

Yoshinobuからの「その考え方はリポのどこかに記録されているのか」という問いで発覚した。決定から数時間しか経っていないのに、既に2つの正本が食い違っていた。

同時に、決定の**根拠**(なぜそうしたか)がリポジトリのどこにもなく、Coordinatorの個人memoryにしか存在しないことも判明した。`docs/ai/memory-classification.md`自身が「subagentの判断が変わる知識はリポジトリへ書く」と定めているのに、それに反していた。

## 適用

安全境界・承認フロー・禁止事項を変更する決定を実施したら、着手前に次を機械的に洗い出す。

```
grep -rn "<変更した境界のキーワード>" docs/ai/ CLAUDE.md AGENTS.md skills/
```

対象の典型は次の4層。上位ほど見落とすと影響が広い。

1. `docs/ai/core.md`(全Roleが最初に読む共通原則) — **最も見落としやすく、最も影響が大きい**
2. `docs/ai/roles/*.md`
3. `docs/ai/policies/*_policy.md`、`docs/ai/context/`
4. `skills/*/SKILL.md`、`CLAUDE.md`

あわせて、決定の**根拠と見直し条件**を`docs/ai/memory/decisions/`へ書く。運用上の境界そのものは正本(通常はRole文書かPolicy)に置き、decisions側へ複製しない。

## 根拠2(2026-07-27、月次Knowledge振り返りの無人実行) — 目視の掃引は3回失敗した

同じセッション内で、掃引漏れを3回起こした。いずれも「直したつもり」で目視確認していた。

1. **廃止した安全根拠の残存**: 書込境界を`--disallowedTools`(denylist)からallowlistへ変えた際、`tasks/main.yml`と`docs/ai/role-routing-index.md`は直したが、`review-prompt.md.j2`だけ「`--disallowedTools`で技術的にも塞いである」が残った。**これは無人LLMが毎月読む当のファイル**であり、廃止した機構を現在形で信じ続けることになる。独立レビューが検出。
2. **別の誤った根拠**: `--setting-sources ''`を導入して`.claude/settings.json`を読み込まなくしたのに、ヘッダコメントに「commit/pushはsettings.jsonのdenyが効く」が残っていた(実際に効いていたのはBash全面禁止)。自分で発見。
3. **撤回した規範の残存**: Incidentの記録タイミングを「修正完了後に1回」から「気づいた時点で捕捉」へ変えた際、`skills/incident-recording/SKILL.md`・`incidents/README.md`・promptは直したが、`docs/ai/memory-classification.md`の別セクションに旧ルールがそのまま残っていた。自分で発見。

**教訓の更新**: 掃引は目視でなく`grep`等で機械的に行い、**撤回した文言そのものを検索語にして残存ゼロを確認する**。「直した箇所を数える」のではなく「古い記述が1つも無いことを示す」。上記3件はいずれも、変更した箇所の周辺だけを見ていたために漏れた。

対象には**実装コメント・promptテンプレート・正本文書のすべて**を含める。特にAIが読むファイル(prompt、SKILL.md、CLAUDE.md)に古い規範が残ると、人間が気づかないまま judgment が汚染され続ける。

## 関連

- `skills/document-norm-review/SKILL.md` — **規範文書レビューの手順の正本**(2026-07-27新設)。本Lessonの掃引作法は同Skillの「前提」節と欠陥クラス3へ取り込み済み。手順を本Lesson側へ複製せず、事例(根拠)としてここを残す。
- `docs/ai/memory/lessons/verify-the-outside-of-a-claimed-boundary.md`(境界の検証そのものの落とし穴)
- `docs/ai/memory/decisions/approval-authority-for-real-host-operations.md`(この掃引の対象となった決定)
- `docs/ai/memory/lessons/multilayer-escaping-and-novel-stack-verification.md`(同クラス全面掃引という同じ発想を、実装の欠陥クラスに適用したもの)

## 再発記録

**機械が追記する節である。人は手で書かない。** 契約(何を記録し、何を記録しないか)は `docs/ai/memory-classification.md`「`lessons/`の「再発記録」節」が正本。

| 日付 | 何に対して踏んだか | 反した規範 | 気づかせたもの |
|---|---|---|---|
| 2026-09-02 | loki-errorsのdispatch・helperを追加した一方、一次調査LLMが読むAGENTS.md.j2を2語のまま残した。 | AGENTS.md.j2は一次調査エンジンが利用可能な調査語彙を示す規範であり、追加した語彙との同期が必要 | Claude側ReviewerとCodex Reviewer |
