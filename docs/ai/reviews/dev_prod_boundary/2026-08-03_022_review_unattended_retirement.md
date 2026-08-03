# Review: 無人 Claude Code セッションの廃止(transfer段退役 + 月次評価の`claude -p`廃止)

日付: 2026-08-03 (JST)
対象: 未commit作業ツリー全体(直前commit `7904ba2`)。Policy改訂、`roles/knowledge_review/`、`playbooks/knowledge_review.yml`、`docs/ai/role-routing-index.md`、`docs/ai/memory-classification.md`、`skills/incident-recording/SKILL.md`、`docs/ai/status.md`、`playbooks/incident_evaluation.yml`削除、`playbooks/README.md`、`roles/incident_capture/defaults/main.yml`(保持期間30→90日)
レビュー方式: 独立レビュー(本レビューはこの変更の実装に関与していない)
入力: `git status` / `git diff`(全ファイル)、`docs/ai/policies/incident_capture_policy.md`現物、`docs/ai/reviews/dev_prod_boundary/2026-08-03_019_〜021_`

## Summary

パイプラインを4段→3段へ縮小する変更は、規範(Policy/role-routing-index/memory-classification)・コード(`roles/knowledge_review`)・成果物(削除したtemplate/tasks)のあいだで概ね一貫しており、依頼書の検査項目1〜5(退役の完全性、退番ID非参照、Policy整合、取得失敗/0件の区別、保持期間と見直し周期の関係)は機械的な掃引で問題を検出しなかった。

一方、`docs/ai/memory-classification.md`に、**今回削除したファイルの一節を指したまま残る宙ぶらりん参照**を1件検出した(Critical)。また、Policy自身の`## 9. 参照`にある注記文言と、`roles/incident_capture/defaults/main.yml`のPolicy ID引用に、それぞれ古い前提を引きずった記述の残存・誤引用を検出した(Major 2件)。N1〜N4の判断はいずれも支持できる根拠を確認した。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---|---|---|
| 1 | `docs/ai/memory-classification.md` | 103 | 「Context陳腐化チェック」の詳細説明を`roles/knowledge_review/templates/review-prompt.md.j2`「Context陳腐化チェック」節に委ねているが、**この差分でそのファイル自体を削除している**(`git status`: `deleted: roles/knowledge_review/templates/review-prompt.md.j2`)。本行は今回の差分で修正されたmemory-classification.mdの同一ファイル内にありながら未更新で残った。宙ぶらりん参照であるだけでなく、**Context陳腐化チェックが何を検査するかという規範内容そのものが、移設先なしに消えている**(欠陥クラス1・2の複合)。無人LLM前提で書かれていたprompt節を削除した以上、「Context陳腐化チェックは今後誰が・どう行うか」(そもそも継続するのか)を明示しないと、この段落は実施不能な指示のまま残る | Critical |

## Suggestions (Major相当。ブロッキングではないが同一クラスの欠陥)

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 2 | `docs/ai/policies/incident_capture_policy.md` | 153 | `## 9. 参照`のADR-005注記が「出力先。**IC-007により前提が変わったため再検討中**」のまま。ADR-005は転送段(quory→ansy)の置き場所を決めたADRであり、**その転送段自体が今回の改訂で消滅した**(§4「転送の規律」節ごと削除、IC-012/014/015/031/033退番)。「再検討中」は2026-07-31時点の注記であり、今回の変更後は「転送段の消滅によりADR-005は前提ごと成立しなくなった(supersede対象)」という状態のはずで、「まだ検討中」という現状の文言は読み手に誤った印象(近く転送先が決まる)を与える。ADR-005自身のStatus行、またはこの参照注記のどちらかを更新するべき | 規範の消失/撤回した根拠の残存(欠陥クラス3) |
| 3 | `roles/incident_capture/defaults/main.yml` | 63 | 保持期間90日の根拠として`incident_capture_policy.md IC-039`を引用しているが、**IC-039は「同一事象に対して一次調査を二重に起動しない」条項**であり、保持期間・見直し周期とは無関係。この変更が実際に依拠すべき条項は`IC-043`(「証拠は quory の1コピーしか存在しない。保持期間の満了が、そのまま証拠の喪失である…見直しの周期を保持期間より長くしない」)である。依頼の検査項目5(保持期間90日と見直し周期の関係がIC-043の要求を満たすか)を機械的に辿ろうとする読み手が、この引用を辿るとIC-039へ迷い込み、実際の根拠条項に到達できない | Policy ID誤引用(トレーサビリティの欠陥) |

## What Looks Good

- **退役の完全性(検査項目1)**: `claude -p` / `ABORTED_DIRTY` / `knowledge_review_allow_dirty` / `job-settings.json.j2` / `incident-job-settings.json.j2` / `review-prompt.md.j2`(memory-classification.md L103を除く)/ `incident-review-prompt.md.j2` / `incident_evaluation.yml` / `incident_index_write.yml` / `--add-dir` / `disallowedTools`(document-norm-review skill内の自己言及を除く)を機械的にgrepし、`docs/ai/reviews/`配下の履歴記録(意図的に過去のまま残るべきもの)を除いて残存が無いことを確認した。`docs/ai/role-routing-index.md`から「無人実行されるCoordinator」節が消え、「現行体制」の記述(常駐する識別子は`claude`のみ)と矛盾なく整合している。
- **退番ID非参照(検査項目2)**: IC-012 / IC-014 / IC-015 / IC-025 / IC-031 / IC-033 を`docs/ai/`・`skills/`・`roles/`・`playbooks/`全体でgrepし、変更履歴表内の記述(削除の記録として正しい)以外の本文参照が無いことを確認した。ADR-005本文には退番IDへの言及が残るが、これは**過去のADR(決定当時の記録)であり規範本文ではない**ため、欠陥クラス3の対象には当たらないと判断した(ただしSuggestion #2のとおりADR-005自体の現況表示は古い)。
- **通知の取得失敗/0件区別(検査項目4)**: `roles/knowledge_review/tasks/incident_metrics.yml`が`knowledge_review_incident_metrics_bundle_list_ok`(rc==0の成否)を基準に`bundle_total`を`None`(失敗)と`0`(成功して0件)で明確に分岐させ、`playbooks/knowledge_review.yml`のSlackメッセージも`FETCH_ERROR`側で「件数・経過日数は取得できていません(0件ではなく取得失敗です)」と明示している。取得失敗時は`slack_channel: alerts` / `status: warning`に倒し、`incident_notify_summary`が`FETCH_ERROR`を`NO_DATA`より先に判定する実装になっており、静かに0件へ落ちる経路を確認しなかった。
- **保持期間と見直し周期の関係(検査項目5)**: `incident_capture_retention_days`を30→90日に延長(`roles/incident_capture/defaults/main.yml`)。月次見直しの周期(約30日)はこの90日を大きく下回り、IC-043「見直しの周期を保持期間より長くしない」を満たす。実装側(`knowledge_review_incident_retention_days: 90`)も同値で複製されており、複製の理由と不一致時の実害の無さ(表示専用であり削除処理は`incident_capture`側の実値で行われる)がコメントで明示されている。
- **Policyとコードの整合(検査項目3)**: IC-005(LLMは一次調査のみ)・IC-043・IC-044(差分カウント)の3条項について、`roles/knowledge_review/`の実装(`claude -p`の完全廃止、`incident_notify_index.bundles_new_since_last_notify`のバンドルID比較によるIC-044実装)が矛盾なく対応することを確認した。
- **N1〜N4の判断**: いずれも現物で裏を取れた。N1(lessonファイル`claude-code-unattended-session-confinement.md`保持)はIC-018が今も同ファイルを正本として参照しており妥当。N2(`incident_evaluation.yml`削除)は`playbooks/README.md`の索引更新と整合し、依存していた`knowledge_review_incident_eval_enabled`変数への参照が他に残っていないことを確認した。N3(Policy §8から4項目除去)は該当4項目がいずれも退番IDまたは決着済み論点への言及であったことを確認した。N4(IC-018不変更)はdiffで確認済み。
- **規範文書への経緯・根拠の埋め込み回避(検査項目6)**: `docs/ai/policies/incident_capture_policy.md`の本文(IC条項)には日付・決定主体の注記が無く、変更履歴表にのみ集約されている(2026-08-02の整理規律を踏襲)。`docs/ai/role-routing-index.md`・`docs/ai/memory-classification.md`の編集箇所も同様に指示のみで、経緯の埋め込みは見られなかった。

## 確認していないこと(未確認事項)

- `playbooks/incident_sync_teardown.yml`の`become: true`化(quory側鍵material削除)が実ホストで正しく動作するかは、状態を変えない確認の範囲を超えるため検証していない(Testerの領域)。
- `docs/ai/adr/005-auto-incident-filing-destination.md`・`009-per-incident-investigation-runtime.md`本文全体の現況(Status行以外)の逐語点検は行っていない。ADRは決定当時の記録として残るものという前提で、Policy側からの参照注記(Suggestion #2)のみを指摘対象とした。
- `skills/incident-recording/SKILL.md`の1行変更以外の全文は、今回の差分に含まれる範囲のみ確認した。

## Verdict

**Request Changes**(Critical 1件)。Critical #1(`docs/ai/memory-classification.md:103`の宙ぶらりん参照+Context陳腐化チェック内容の消失)は、退役の完全性という依頼の最重要検査項目に直接該当するため先に解消を要する。Major相当のSuggestion #2・#3は、トレーサビリティの欠陥であり実害は限定的だが、同一commitでの修正を推奨する。

---

## Coordinator の処置(2026-08-03)

| finding | 処置 |
|---|---|
| **Critical**(`memory-classification.md` が削除済み prompt へ「Context陳腐化チェック」の詳細を委ねていた) | **修正した。** 手順4ステップを同ファイルへ**インライン化**し、参照を無くした。あわせて直前の「自律の境界」段落も直した — 無人セッション前提(`policy-proposal` への書き出し、commit/push禁止、作業ツリーが汚れていたら中止)がそのまま残っており、**Critical と同じ取り残しだった**。書き出し先だけを述べる形に縮めた |
| **Major**(Policy §9 の ADR-005 注記が古い前提) | **修正した。**「IC-007により前提が変わったため再検討中」→「転送段の消滅により前提ごと成立しない」 |
| **Major**(`incident_capture/defaults/main.yml` が IC-039 を誤引用) | **修正した(IC-043 へ)。この誤りは Coordinator 自身が書いたものである。** 同日、Policy 改訂案で IC-039 / IC-040 が使用済みだったことを自分で発見して振り直したにもかかわらず、**別ファイルへ同じ番号を書いていた。** 番号の衝突を1箇所で直しても、同じセッション内の他の箇所へ波及させていなければ意味がない |

**Critical の性質について。** 指摘は「宙ぶらりん参照」として挙がったが、実害はそれより重い — **参照先が消えたことで、規範の内容そのもの(何を検査するのか)が移設先なしに失われていた。** 削除された prompt は規範文書ではなく実装物だったため、規範の削除掃引の対象から外れていた。**規範が実装物へ内容を委ねている箇所は、実装物を消すときの掃引対象に入る。**
