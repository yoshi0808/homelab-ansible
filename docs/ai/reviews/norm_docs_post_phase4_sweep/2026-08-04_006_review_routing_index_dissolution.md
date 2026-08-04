# Code Review: `docs/ai/role-routing-index.md` の解体(削除・core.md/coordinator.mdへの移設)

## Summary

`docs/ai/role-routing-index.md`(削除前64行)を項目ごとに読み、`git diff --cached` の28ファイルへ逐一突き合わせた。**規範の消失は無い。** 新設節も無く(`docs/ai/status.md` の「節は増えていない」という記述は現物と一致)、宙ぶらりん参照も検出しなかった。機械ゲート(`scripts/check-doc-consistency.py` check2)は実行して確認し、検査対象・検査ロジックとも実質的に弱まっていない。**Critical 0件、Suggestion 1件**(`core.md`内での軽微な二重化)。

## 突き合わせの方法

1. `git show HEAD:docs/ai/role-routing-index.md` で削除前の全文(64行)を読み、段落・表の行単位で項目を切り出した。
2. 各項目について、`git diff --cached docs/ai/core.md` と `git diff --cached docs/ai/roles/coordinator.md` の追加行に対応する記述があるかを照合した。文言が異なる場合は意味が保存されているかを判定した。
3. 削除した文言そのもの(`role-routing-index`、略記`本index`、`次の3つを読む`)を検索語として、`docs/ai/reviews/` `docs/ai/memory/` `docs/ai/adr/` を除く全live層(`docs/ai/`, `skills/`, `.claude/`, `scripts/`, `roles/`, `playbooks/`, `inventories/`, `CLAUDE.md`, `AGENTS.md`)を`grep -rn`で機械的に掃引した。
4. `scripts/check-doc-consistency.py --repo-root .` を実際に実行し(exit 0、check1〜3すべてOK)、`scripts/tests/fixtures/run-fixture-checks.sh` も実行して5フィクスチャすべてが期待exit codeどおりに失敗/成功することを確認した(この2つはgit indexおよび使い捨てtemp repoしか読まない。対象ファイルは1文字も変更していない)。
5. `check_agent_model_effort` の`find_table`ロジックを読み、`docs/ai/roles/coordinator.md`内の2つの表(「起動できるRole」表と「モデル・effort配分」表)のうち、ヘッダ列に`model`/`effort`を含む後者だけが一意にマッチすることをコードとテスト実行の両方で確認した。

## 項目単位の突き合わせ結果(削除前 → 移設先)

| 削除前の項目 | 移設先 | 判定 |
|---|---|---|
| 「現行体制」(常駐識別子はclaudeのみ、他Roleはその場起動) | `coordinator.md`「起動できるRoleと、その実現方式」冒頭 | 保存 |
| Role/モデル/実現方式の表(Coordinator行含む) | `coordinator.md`のRole/実現方式表 + 「モデル・effort配分」節の文章化(Coordinatorのモデル原則) | 保存(表現形式のみ変更) |
| Reviewer行の「同一subagentを使い回さないことで独立性を担保する」 | `coordinator.md`表内に同旨を維持 | 保存 |
| Tester行の「実ホストへ到達してよい唯一のRole」 | `coordinator.md`表内に維持 | 保存。ただし後述の通り、この文自体はTester自身の行動を制約しない記述的文言であり、Tester自身のagent定義の必読リストには入らない(下記「気づいた点」参照) |
| Tester行の「Implementer/Reviewer/Auditorは実ホストへansibleを実行しない」 | 削除、移設先の記述なし | **消失ではない** — `implementer.md`/`reviewer.md`双方の禁止事項節に同一趣旨の禁止(「実ホストへansibleを実行しない。状態を変えない確認も含む」)が既に独立して明記されており、そちらが元々の正本。ここでの記述は説明の重複だった |
| 「モデル・effort配分」節本文・表 | `coordinator.md`へほぼ同一文言で移設 | 保存 |
| 「Agent定義との関係」節(実行機構のみ持つ、agent定義の作成・編集は次セッションから効く 等) | `coordinator.md`へほぼ同一文言で移設 | 保存 |
| 「証跡の扱い」節 | `core.md`「AI間連携と成果物」の既存bulletへ追記(「実質的な証跡は`docs/ai/reviews/<target>/`配下のファイル…」) | 保存。「subagent自身の思考過程・対話ログは永続化されない」は`core.md`に元々あった文と重複するため吸収不要と判断した跡が見え、実際に元の文(115行目)がそのまま残っている |
| 「正本の優先順位」表(6行) | 大半は`core.md`「目的と正本」に元々あった箇条書きと重複していたため、新規追加は「案件固有の要求・成果物」行の`fallback`文言(「関係しそうなreviewsを無差別に探索しない」)のみ | 保存。ただし下記Suggestion参照 |
| 「作業開始時の解決手順」6ステップ | `core.md`「作業時に読む情報」の既存7ステップへ統合。旧手順3(「本indexで実現方式を確認する」)のみ削除し、他はそのまま順送り | 保存。手順3の削除は意図的(`core.md`96行目の新設文「Roleの実現方式は`coordinator.md`を正本とする。起動を決めるのはCoordinatorであり、他のRoleはこれを判断に使わない」で、この情報が構造的にCoordinator限定であると明示しており、Implementer/Reviewer/Tester/Auditorがこのステップを失っても機能に影響しない) |

**識別子・Role対応・実現方式を「推測なしに解決する」という冒頭の目的文自体、および「案件owner」という語** は移設先のどこにも出てこないが、`grep`で確認した限り「案件owner」は現行の単一Coordinator体制(2026-07-29 Tech Lead廃止済み)以前の複数trio運用の残存語彙で、削除前ファイル自体もこの語を定義せず1回言及するのみだった。実質的な規範が載っていた形跡はなく、消失として扱わなかった。

## 二重化の確認

- `core.md`内で新規に追記した文と、既存の文が意味的に重複していないかを全文通読で確認した。**1件、軽微な重複が新たに生じている**(Suggestion S1、下記)。
- `coordinator.md`側は新設節(105行台)であり、同ファイル内の既存節(「実ホストへの非冪等操作の承認」等)と内容の重複は無い。

## 参照の張り替え漏れ(掃引結果)

`role-routing-index`・`routing-index`・`routing index`・`本index`・`次の3つを読む`のいずれでも、`docs/ai/reviews/` `docs/ai/memory/` `docs/ai/adr/` を除くlive層に残存を確認しなかった。唯一のヒットは`docs/ai/status.md`の「前提だった`role-routing-index.md`の解体は2026-08-04に完了した」という過去形の記述で、これは正しく現状を説明しており宙ぶらりん参照ではない。

張り替えを確認した参照元(いずれも新しい参照先が実在し、内容と整合): `CLAUDE.md`、`AGENTS.md`、`docs/ai/core.md`、`docs/ai/roles/{implementer,reviewer,tester,auditor}.md`、`docs/ai/context-classification.md`、`docs/ai/context/system/overview.md`、`docs/ai/role-context-matrix.md`(該当行を削除するのみで妥当)、`.claude/agents/auditor.md`、`scripts/check-doc-consistency.py`、`scripts/git-pre-commit-check.sh`(コメントのみ)、`scripts/tests/fixtures/`5件全て(リネーム後のファイル名・内部リンク・README記述)。

## 機械ゲートの追随

`scripts/check-doc-consistency.py` check2は、参照パスを`docs/ai/role-routing-index.md`から`docs/ai/roles/coordinator.md`へ変更しただけで、検査ロジック(`find_table`によるヘッダ`role`/`model`/`effort`一致検索、role集合の差分比較、model/effort値の完全一致比較)は無変更。`docs/ai/roles/coordinator.md`には表が2つ(「Role/実現方式」と「Role/model/effort」)あるが、`find_table`はヘッダに`model`と`effort`を両方含む表だけを拾うため一意に「モデル・effort配分」表を検出する。実行して確認: `python3 scripts/check-doc-consistency.py --repo-root .` → 3チェックすべてOK、exit 0。`scripts/tests/fixtures/run-fixture-checks.sh` → 5フィクスチャすべて期待どおりのexit code。**検査対象・検査内容とも実質的に弱まっていない。**

## Critical Issues

なし。

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| S1 | `docs/ai/core.md` | 13, 86 | 13行目「関係しそうなreviewsを無差別に探索しない。」(今回の移設で新規追加)と、86行目「関連しそうなContextやreviewsを無差別に探索しない。」(既存)がほぼ同内容を重複して述べている。移設元の役割インデックスにあった`fallback`文言をそのまま吸収した結果、既存の同旨の注記と70行ほど離れた場所で二重化した。指摘対象がPolicy本文でも安全境界でもなく、実害(誤読・矛盾)は無いため blocking ではない。13行目を削除するか、86行目へ一本化することを推奨する | duplication |

## What Looks Good

- `role-routing-index.md`削除前の64行を項目単位で全て追跡でき、規範の欠落は1件も無かった(表内の重複記述の整理のみで、実体としての禁止・許可は各Role文書側に既に独立して存在していた)。
- `core.md`は新設節を1つも作らず既存節への吸収のみで完結しており、`docs/ai/status.md`の記述(「節は増えていない」)と現物が一致する。
- `coordinator.md`の新設節は既存の「実ホストへの非冪等操作の承認」節と内容が競合・重複しない形で挿入されている。
- 機械ゲート(check-doc-consistency.py check2)とフィクスチャ5件は実際に走らせて確認し、参照パスの変更後も検査対象・ロジックとも劣化していない。
- CLAUDE.md/AGENTS.mdとも、削除したファイルへの参照を機械的に除去し、CLAUDE.mdは「起動できるRoleとモデル配分」を`docs/ai/roles/coordinator.md`にある旨を明記する形で更新されている。
- Implementer/Reviewer/Tester/Auditorの各agent定義(`.claude/agents/*.md`)には元々`role-routing-index.md`への必読参照が無く(auditor.mdのみ補足参照があった)、削除の影響を受ける必読経路は無い。

## 未解決事項

- S1は軽微な重複であり、この案件の範囲内で直すか次の`core.md`圧縮作業(`docs/ai/status.md`に着手候補として記載済み)へ含めるかはCoordinatorの判断に委ねる。
- 「案件owner」という語が旧ファイルの冒頭文にのみ現れ定義を持たない状態で消えた点は、現行の単一Coordinator体制と整合しており実害は無いと判断したが、過去のtrio運用に由来する語彙が他のlive文書に残っていないかは今回の掃引範囲外(役割ルーティングに限定して掃引した)であり、未確認。

## Verdict

Approve

---

## Coordinatorによる処置(2026-08-04)

**S1を受け入れて是正した。却下した指摘は無い。**

`docs/ai/core.md` L13 に今回足した「関係しそうなreviewsを無差別に探索しない」を削除した。同じ規範は L86(現 L85)が既に、より広い形(Contextも含む)で持っている。**次工程の「core.mdの圧縮」へ送らず、この案件で直した** — 今回の吸収作業そのものが生んだ二重化であり、持ち越すと「元からあったもの」と区別がつかなくなるため。

未解決事項として挙がっていた「案件owner」という語彙の消失は、実害なしという判定に同意する。旧trio運用の残存語彙であり、現行の単一Coordinator体制で定義を持たない。他のlive文書への残存確認は本案件の範囲外とし、`docs/ai/status.md` Next の「Role文書5本のプロンプト最適化(継続案件)」で扱う。

是正後に `scripts/check-doc-consistency.py`(stage後)と `scripts/tests/fixtures/run-fixture-checks.sh` を再実行して確認した。
