# 第2束フェーズ1(軽い束)実装記録(2026-08-25)

対象: `2026-08-25_004_fix_scope.md`「第2束」1.「軽い束」の5項目(P3-1 / P5-1 / P5-2 / S5-2 / P1-4)。

## 変更ファイル一覧

- `docs/ai/core.md`
- `docs/ai/policies/execution_boundary_policy.md`
- `docs/ai/policies/autonomous_recovery_policy.md`
- `docs/ai/roles/reviewer.md`
- `skills/duplication-reuse-check/SKILL.md`

## 項目ごとの充足

| 項目 | 対応 | 参照先の実在確認 |
|---|---|---|
| P3-1 | core.md「Gitの扱い」の`git commit`/`git push`行を「承認区分・実行主体はEXEC-030を正本とする」の1行ポインタへ縮小。EXEC-030表の当該行へ、core側にしか無かった「subagentは承認の有無にかかわらず行わない」を追記。stage内容提示義務は元々EXEC側にあり無改変 | EXEC-030マーカーとポインタ先の行を確認済み。両要素(stage提示義務・subagent禁止)が同一行に揃っていることを確認 |
| P5-1 | EXEC-080/081の本文2段落を、core.md「安全機構がブロックしたとき」への1行ポインタへ統合(マーカーは両方残す)。EXEC-083本文も同節への1行ポインタへ。EXEC-082(identity昇格禁止)は無改変で残置 | core.md「安全機構がブロックしたとき」節(該当5行)が変更前のまま存在することを確認済み。ポインタ先に元の規範(ブロック時の報告義務・妥当性不判定・目的問い直し・設定確認手順)が全て残っていることを逐語突き合わせ済み |
| P5-2 | AR-102後段「境界は能力の不在で作る」を`docs/ai/core.md`「安全機構がブロックしたとき」への1行ポインタへ改め、前段(execpolicy禁止)は無改変で残置 | 同上の節が現存することを確認済み |
| S5-2 | duplication-reuse-check SKILLの「Reviewerは照合のみ」「全リポジトリ横断検索はReviewerに行わせない」の規範本文を、`docs/ai/roles/reviewer.md`「禁止・エスカレーション」への1行ポインタへ置換。reviewer.md側へ同内容の禁止事項を新規bulletとして追加。「発見・指示はCoordinatorが担う」はSKILLに工程記述として残置 | reviewer.mdの新規bulletを確認済み。SKILL側は権限の正本を名乗らない文言(「本SKILLは権限の正本を名乗らない」)へ変更 |
| P1-4 | execution_boundary_policy.md:3とcore.md:82の「全Roleが起動時に読む」を「開発工程のRole(Auditorを除く)が起動時に読む」へ書き換え、絞り込みの根拠として`docs/ai/role-context-matrix.md`と`docs/ai/roles/operator.md`「この文書の位置づけ」を1行で指す形にした。auditor.md・matrixは無変更 | matrix「Auditorの参照範囲」節(execution_boundary_policy.mdを含まない限定列挙)、operator.md「この文書の位置づけ」節(Operatorは本リポジトリを読まない旨)がともに現存し、絞り込みの実質根拠として成立していることを確認済み |

各Policy改訂は変更履歴表へ既存書式で追記した(execution_boundary_policy.md v1.4に3項目分をまとめて1行、autonomous_recovery_policy.mdへ日付行1行)。いずれもルールID(EXEC-xxx/AR-xxx)の新設・退番は行っていない。EXEC-080/081はcore.mdへのポインタとして1文へ統合したため、EXEC-080とEXEC-081の本文はそれぞれ独立した文言を持たなくなった(2つのマーカーが同一のポインタ文を指す状態)。この旨をv1.4の変更履歴行に明示した。

## 自己検証

- 5項目すべてについて、ポインタの指す先(節見出し・ルールID)が実在し、内容が実際に書かれていることを上表の「参照先の実在確認」欄で個別に確認した(マーカーの実在だけでなく、指した先の規範本文を読んで確認)。
- 統合・移設で片側にしか無かった要素の逐語突き合わせ:
  - P3-1: `subagentは承認の有無にかかわらず行わない`(core.md旧文)と`stageした内容の分類とcommitメッセージ案を提示する`(EXEC-030旧文)の両方が、改訂後のEXEC-030単独行に揃っていることを確認。
  - P5-1: core.md「安全機構がブロックしたとき」の5行(ブロック時の報告義務・妥当性不判定・目的の問い直しと検証設計の組み替え・報告義務・設定確認手順)を、削除したEXEC-080/081/083の本文と1行ずつ突き合わせ、内容の欠落がないことを確認(元々ほぼ逐語のため、削除側に固有の要素は無かった)。
- `python3 scripts/check-doc-consistency.py` → `[check1] OK (114 compared)` / `[check2] OK (8 compared)` / `[check3] OK (104 compared)`、exit 0。
- `.claude/skills/` の相対symlinkは全て解決可能(壊れているものなし)。
- repo全体(`docs/` `skills/` `.claude/` `CLAUDE.md` `AGENTS.md`)を`全Role`でgrepし、execution_boundary_policy.mdを「全Roleが読む」と主張する箇所が本実装後に残っていないことを確認した。残る「全Role」の用例はcore.md自身の共通原則の話・decoyの話・memory-classification・lessons(過去記録)・auditor.mdのcore.md読了記述・agent定義のcore.md参照など、execution_boundary_policy.mdの読み手主張とは無関係であることを1件ずつ確認した。

## 未解決事項

なし。5項目とも方向どおりに実装完了。第2束の残り(中2件・S2-3・P1-8/P5-3、および越境5件のうち本フェーズ対象外の部分)は本記録の対象外。
