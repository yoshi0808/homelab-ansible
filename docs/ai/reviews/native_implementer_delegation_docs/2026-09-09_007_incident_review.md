## Code Review: 計画外事象(バッククォート検索によるshellコマンド実行)の記録

### Summary

005 Approve後に発生した計画外事象(旧語掃引の検索パターン中のバッククォートがshellへコマンドとして評価された)の記録一式(Incident 2件、Lesson 1件、案件003/006の計画外事象節)を確認した。`docs/ai/memory-classification.md`が定める昇格順序・二重保持禁止・被参照確認のいずれにも適合し、4記録間(2026-09-08 Incident・2026-09-09 Incident・Lesson・案件003/006)の事実記述は相互に矛盾しない。元のprompt修正(Implementer委任経路の規範現行化、4ファイル)への影響は無い。Critical/Major無し。

### Critical Issues

なし。

### Major Issues

なし。

### 確認条件ごとの結果

**1. memory-classificationの昇格順序・二重保持・参照**

- 昇格条件(`docs/ai/memory-classification.md`3節「Incident ↓ 同種の問題が2回目以降発生」)に該当する。2026-09-08(git push起動)と2026-09-09(3識別子起動)は同一欠陥クラス(検索パターン中のバッククォートをダブルクォート内に置きshellへ渡した)の2件目であり、即時昇格の判断根拠として妥当。
- 昇格順序(「①昇格先へ本文と根拠を書く→②元を1行へ縮約する」)は、現在の終端状態で確認できる範囲では満たされている——`docs/ai/memory/lessons/shell-search-patterns-must-not-be-evaluated.md`の「根拠」表に両日付・事象・結果が具体的に記載されたうえで、両Incidentファイルが「Lesson `<path>`へ昇格済み。」の1行のみへ縮約されている。**作業順序そのもの(先に本文を書いたか)はagmsgのメッセージ・shell履歴からは確認できず未確認**だが、終端状態は矛盾しない。
- 二重保持は無い。両Incidentファイルの本文はLessonへ完全に移送され、元ファイルは既定の1行(`docs/ai/memory-classification.md`3節の書式)だけを残している。
- 被参照確認: `grep -rln`で両Incidentファイルへのパス参照をdocs/ai・skills・CLAUDE.md・AGENTS.md・.claude/全域で検索し、ヒット無し(宙ぶらりん参照は発生していない)。

**2. Incident事実と実行出力の一致**

- 案件`_003_implementation.md`の「計画外事象」節(バッククォート3語のうち2語がnot found、1語でClaude Codeが入力不足で終了、直後の`git status`で想定外変更なし)と、Lessonの「根拠」表2026-09-09行の記述は一致している。
- 案件`_006_closeout.md`の「計画外事象」節は個別の実行結果(3語/2件not found等)を省略した要約だが、`_003`・Lessonの記述と矛盾しない。
- 2026-09-08 Incidentの元内容(縮約前、`git diff`で確認)——SSH設定検査での接続前失敗、HEAD/origin-main一致確認——は、Lesson「根拠」表2026-09-08行の要約と整合する。
- **他セッション(Coordinator/Codex側)が実際に何を実行したかそのものは、本Reviewerのshell履歴には現れないため直接の再現検証はできない**。ただし独立に確認できる事実——現在の`git status`に想定外の変更が無いこと、`git rev-parse HEAD`が`origin/main`(`7fd8c91`)と一致すること——は、両Incidentが主張する「repo変更なし」と一致する。

**3. 元のprompt修正scopeへの悪影響がないこと**

- 対象4ファイル(`docs/ai/roles/coordinator.md`、`docs/ai/context/operations/agent-messaging.md`、`docs/ai/adr/012-role-model-effort-defaults.md`、`docs/ai/status.md`)のdiffを再取得し、005時点で確認した内容と完全に一致することを確認した(新たな変更なし)。
- `python3 scripts/check-doc-consistency.py`: 独立再実行でcheck1/2/3すべてrc=0。
- `git diff --check`: エラー無し。
- `git status --porcelain=v1 --untracked-files=all`で全変更点を確認し、依頼で列挙されたIncident 2件・Lesson 1件・案件003/006・本レビュー成果物以外への変更が無いことを確認した。

### Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `docs/ai/memory/incidents/2026-09-09_backtick-in-search-invoked-local-commands.md` / `docs/ai/memory/lessons/shell-search-patterns-must-not-be-evaluated.md` | ファイル名 | レビュー時点のファイル名はslugにハイフンでなくアンダースコアを使っており、既存の大半と様式が異なっていた。機能に影響しないためnon-blocking | style |

### What Looks Good

- **昇格条件の妥当性**: 「同種の問題が2回目以降発生」という3節の規定にちょうど該当する事例であり、月次振り返りを待たずCoordinatorが即時判断した対応は3節「Incident→Lesson」の規定(条件を満たした時点で判断する)と整合する。
- **Lesson本文の再利用可能性**: 「守ること」節はダブルクォート内バッククォートの危険性を一般化し、識別語分割・実行前確認・誤起動時の確認手順まで含み、注意喚起で終わらない具体性を持つ。
- **既存Lessonとの重複無し**: `docs/ai/memory/lessons/`内で「バッククォート」を含む既存記述(`verify-through-the-consuming-filter.md`)を確認したが、対象が異なる(バッククォート識別子を代用指標として使う際の未検算の話であり、shellが検索パターンを評価する本件とは別欠陥クラス)ため重複ではない。
- **scope**: Incident/Lesson/案件記録の追加編集は依頼で列挙されたファイルのみであり、対象4ファイルへの追加変更・実ホスト操作は無い。

### 確認範囲

- `docs/ai/memory/incidents/2026-09-08_backtick-in-search-invoked-git-push.md`(diffで元内容を含め確認)。
- `docs/ai/memory/incidents/2026-09-09_backtick-in-search-invoked-local-commands.md`(全文)。
- `docs/ai/memory/lessons/shell-search-patterns-must-not-be-evaluated.md`(全文)。
- `docs/ai/reviews/native_implementer_delegation_docs/2026-09-09_003_implementation.md`「計画外事象」節、同`_006_closeout.md`「計画外事象」節。
- `docs/ai/memory-classification.md`3節(昇格・廃止ルール)、`skills/incident-recording/SKILL.md`全文。
- `grep -rln`によるIncidentファイルパスへの被参照検索(dangling reference確認)。
- 対象4ファイルの再diffと005時点内容との突き合わせ。
- `python3 scripts/check-doc-consistency.py`、`git diff --check`、`git status --porcelain=v1 --untracked-files=all`、`git rev-parse HEAD origin/main`。

### 未確認事項

- 昇格作業の実施順序(本文移送が先だったか)そのものは、本Reviewerから直接観測する手段がなく、終端状態からの整合性確認に留まる。
- 2026-09-09 Incidentが記述する実際のshellコマンド実行(3識別子の起動、出力)は、実行主体であった他セッションのターミナル出力そのものを見ておらず、`git status`/`HEAD`一致という間接証拠のみで裏づけている。

### Verdict

Approve(Critical/Major無し)。

### Coordinator対応

Suggestion 1を採用し、両ファイルをハイフン区切りへ改名して全参照を更新した。
