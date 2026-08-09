# Code Review: Semaphore schedules as code requirement 11回目査読

## Summary

前回の`template_id`出所とAC22の時系列は解消した。管理項目更新後にだけ有効化する二段階化の方向も妥当である。ただし、R8-2/R16-2が一段階のeffective desired stateのままでR8-3と矛盾し、`true → false`の適用経路も失われているため、**分類1は1件**残る。

## Critical Issues

### 分類1: requirement段階で直す必要があるもの（1件）

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 75-77, 86, 90, 155-163, 230-243 | **二段階化したのにeffective stateと検証契約が段階別になっておらず、正常な第1段階が失敗し、`true → false`は適用されない。** 既存scheduleが`active:false`、catalogが`true`、R12の4条件成立なら、R8-2のeffective `active`は`true`である。一方R8-3の第1段階は観測値`false`のまま書くため、R16-2がR8-2との完全一致を要求すると正常な第1段階を不一致として停止し、第2段階へ到達できない。逆に既存が`active:true`、catalogが`false`なら、R8-3は第1段階で観測値`true`を維持し、第2段階は有効化専用なので、R12の「`true → false`を即座に確定」とAC17ケース②を実現する段階が無い。**書き込み値とGET検証値を段階別に定義する必要がある。** 第1段階の`active`は「catalogがfalseならfalse、それ以外は観測値」、第2段階は「第1段階で管理4項目の一致を確認済みかつR12再確認済みの場合だけtrue」とする。R16-2は各段階のdesired stateと比較する。さらに第2段階のPUTもR8の単一GET→全フィールド送信を守り、「有効化だけ」はminimal payloadではなく**論理差分がactiveだけ**という意味に固定する。第2段階直前の単一GETで管理4項目が第1段階の検証済み値のまま、かつactiveがfalseであることを確認し、不一致なら有効化せず停止または見送りとする。これにより、第1段階後のUI変更を未検証のまま有効化PUTへ載せない。 | Critical |

## Suggestions

### 分類2: implementまたはtest_planへ送ってよいもの（6件）

第9節の既存6件は、引き続き記載された送り先へ移してよい。追加の分類2 findingは無い。

| # | 引継ぎ先 | 内容 | 判定 |
|---|---|---|---|
| 2 | implement | PUT round-trip、DB構造、19件`task_params`、deep equality、型保持/OQ7 | 後続可 |
| 3 | test_plan | AC15のreachable mockまたはURL判定unit test | 後続可 |
| 4 | test_plan | 結果へ影響しないACの3軸fixture表記統一 | 後続可 |
| 5 | Tester(初回quory) | OQ1の20/19とOQ3のAPI/SQLite突合 | 後続可 |
| 6 | implement | OQ5のtransaction/ETagと残余競合fixture | 後続可 |
| 7 | test_plan | OQ8の孤児行増加・冪等時非増加・cleanup別判断 | 後続可 |

## What Looks Good

- R8-3は、危険な実行パラメータの保存確認より先にscheduleを有効化しない、という必要な順序保証を明文化した。前回Finding #1の原因認識と二段階化の方針は妥当である。
- R8-2は`template_id`をcatalog値から除外し、catalogのtemplate名を当該APIで一意に解決したidと定義した。R1の論理管理項目とAPI比較フィールドの区別も明記され、前回Finding #2は解消した。
- AC21は既存`active:false`、catalog `true`をGivenに固定し、第1段階の保存不一致時に第2段階PUTが0件であることを観測する形になった。
- AC22は処理順を固定し、1件目のPUT成功後に2件目のidentityを変更するため、部分適用済みの事実、残り書き込み中止、非ゼロ終了をそれぞれ観測できる。前回Finding #3は解消した。
- duplication/reuse: 既存playbookとreportの再利用方針に新たな欠落はない。
- security: 秘密候補と判定不能のpreflight停止、canonical URL allowlist、token非記録、DELETE禁止は維持されている。
- Reviewer定型観点: requirement段階のため多層エスケープとshell rc規約は対象なし。`--check`外のPOST/PUT、有効化、write-after-readはACに割り当てられている。例外吸収を成功扱いする要件はない。

## 確認範囲

- 第11稿requirement全文、前回`2026-08-09_011_review_requirement_r10.md`、着手時のworktree status/diff
- R8/R8-2/R8-3/R12/R16-2とAC3/AC6/AC17/AC21の、新規・更新・無効化・有効化の状態遷移
- R3とR8-2のtemplate名から`template_id`への解決契約
- R8のclosed-world部分適用残余とAC22の処理順・観測点
- Semaphore System Context、Ansible test safety policy、既存`semaphore_templates` role/playbook/reportの接続箇所
- duplication/reuseおよびAnsible security観点

## 未確認事項

- Semaphore APIへのGETを含め、API呼出しは行っていない。本文の2.18.4実測値は今回再測定していない。
- Ansibleは実ホスト・decoy・syntax-checkのいずれも実行していない。
- 実装コード、mock方式、deep equality、`task_params` schema、競合注入手段は後続工程の確認対象である。
- commit、pushは行っていない。

## Verdict

**Request Changes** — 分類1は1件。二段階化の方針は正しいが、段階別desired stateと検証値を定義しない限り、有効化の正常系と即時無効化の双方が要件どおりに実装できない。
