# Code Review: Semaphore schedules as code requirement 12回目査読

## Summary

R8-2とR16-2は段階別desired stateへ修正され、第2段階PUTのfull round-trip契約も入った。しかしR8-3の第1段階には旧来の「activeを観測値のまま」が残り、即時無効化と矛盾する。また、第2段階直前drift時の挙動が「停止または見送り」のままでACも無い。したがって**分類1は2件**残る。

## Critical Issues

### 分類1: requirement段階で直す必要があるもの（2件）

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 76-77, 86, 240-243 | **R8-3の第1段階が依然「`active`を観測値のまま」と要求し、R8-2の即時無効化と矛盾する。** API側`active:true`、catalog `false`では、R8-2/R12/AC17ケース②は第1段階のdesiredをfalseとして即時無効化するが、R8-3はtrueのまま送る。どちらを実装しても別のP0要件に違反する。R8-3の第1段階を「`active`はR8-2の第1段階desired（新規false、既存はcatalog falseならfalse、それ以外は観測値）」へ揃える必要がある。 | Critical |
| 2 | 同上 | 77, 90-91, 210-213, 230-243 | **第2段階直前に管理4項目が変わった場合の結果が「停止または見送り」と未決定で、受入条件も無い。** この分岐は、非ゼロで残りの有効化を止める実装と、終了0で当該1件だけを見送って他を有効化する実装の双方を許す。第2段階はR12によりclosed-worldでのみ到達するため、どちらがclosed-worldのfail-closed契約なのかrequirementで決める必要がある。少なくとも、管理4項目を第1段階検証後・第2段階直前に変更するfixtureで、当該有効化PUTが0件、終了コード、残りの有効化PUTを続けるか否か、既に発行済みの第1段階PUTとdrift内容のreportをACとして観測する必要がある。AC16はschedule集合の変化、AC21は第1段階直後GETの不一致であり、この窓の管理項目driftを識別しない。 | High |

## Suggestions

### 分類2: implementまたはtest_planへ送ってよいもの（6件）

第9節の既存6件は、記載された送り先へ移してよい。追加の分類2 findingは無い。

| # | 引継ぎ先 | 内容 | 判定 |
|---|---|---|---|
| 3 | implement | PUT round-trip、DB構造、19件`task_params`、deep equality、型保持/OQ7 | 後続可 |
| 4 | test_plan | AC15のreachable mockまたはURL判定unit test | 後続可 |
| 5 | test_plan | 結果へ影響しないACの3軸fixture表記統一 | 後続可 |
| 6 | Tester(初回quory) | OQ1の20/19とOQ3のAPI/SQLite突合 | 後続可 |
| 7 | implement | OQ5のtransaction/ETagと残余競合fixture | 後続可 |
| 8 | test_plan | OQ8の孤児行増加・冪等時非増加・cleanup別判断 | 後続可 |

## What Looks Good

- R8-2は第1段階と第2段階のdesired `active`を分け、第1段階では有効化せず、第2段階は管理4項目一致済みかつR12再確認済みの場合だけ実行すると定めた。
- R16-2は各POST/PUT後の単一GETを、その段階のdesired stateと比較する形になり、正常な第1段階を第2段階desiredと誤比較する前回の欠陥を解消した。
- R8-3は第2段階でも単一GETを取り直して全フィールドを送り、「有効化だけ」がminimal payloadではなく論理差分を意味すると明記した。`task_params`消失を招く短いpayloadを許さない。
- 第2段階直前に管理4項目とactiveを再確認することで、第1段階後のUI変更を無条件に有効化PUTへ載せない観測点を追加した。Finding #2は、その検出後の結果を一意にすることだけを求める。
- `template_id`の出所、AC21の第2段階PUT 0件、AC22の部分適用時系列は前稿の修正を維持している。
- duplication/reuse: 既存playbookとreportの再利用方針に新たな欠落はない。
- security: 秘密候補と判定不能のpreflight停止、canonical URL allowlist、token非記録、DELETE禁止は維持されている。
- Reviewer定型観点: requirement段階のため多層エスケープとshell rc規約は対象なし。`--check`外のPOST/PUT、段階別検証、有効化はAC群に現れるが、Finding #2の窓だけnegative ACが無い。無音化についても同Findingの「見送り」が成功終了と判定不能を混同し得る。

## 確認範囲

- 第12稿requirement全文、前回`2026-08-09_012_review_requirement_r11.md`、着手時のworktree status/diff
- R8/R8-2/R8-3/R12/R16/R16-2とAC6/AC16/AC17/AC21の状態遷移・API call順序
- 第1段階の`true → false`と、第1段階検証後から第2段階PUTまでのUI競合
- Semaphore System Context、Ansible test safety policy、既存`semaphore_templates` role/playbook/reportの接続箇所
- duplication/reuseおよびAnsible security観点

## 未確認事項

- Semaphore APIへのGETを含め、API呼出しは行っていない。本文の2.18.4実測値は今回再測定していない。
- Ansibleは実ホスト・decoy・syntax-checkのいずれも実行していない。
- 実装コード、mock方式、deep equality、`task_params` schema、競合注入手段は後続工程の確認対象である。
- commit、pushは行っていない。

## Verdict

**Request Changes** — 分類1は2件。段階別desired stateの中核は整ったが、第1段階の旧記述と、第2段階直前driftの未決定分岐を解消する必要がある。
