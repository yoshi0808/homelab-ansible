# Code Review: Semaphore schedules as code requirement 10回目査読

## Summary

前回分類1の2件について、effective desired stateの導入とnegative ACの追加は確認した。ただし、管理項目更新と`false → true`を同じPUTに載せる現契約では、write-after-readが不一致を検出する前にscheduleが有効化され得る。さらにeffective stateの`template_id`の出所がR3と矛盾し、AC22は既発行PUTの観測を成立させないGivenになっている。したがって**分類1は3件**残る。

## Critical Issues

### 分類1: requirement段階で直す必要があるもの（3件）

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 75-76, 85-90, 229-232 | **write-after-readの失敗時には、同じPUTによる有効化を既に取り消せない。** R8-2はR12の4条件成立時、既存scheduleのeffective `active`を`true`にするため、`task_params`等の更新と`false → true`が1つのPUT payloadに同居する。APIが未知keyを捨てても、同じPUTの`active:true`は受理され得る。R16-2が直後GETで不一致を検出した時点ではscheduleは既に有効であり、「不一致なら当該scheduleを有効化しない」もAC21の「activeはtrueにならない」も保証できない。HTTP成功を保存成功とみなさない方針を実効化するには、少なくとも **(1) `active`を観測値のまま管理4項目を書いてGET一致を確認、(2) 一致確認後にだけR12の条件を再確認して有効化PUT、(3) そのPUTも直後GETで検証** という二段階契約が必要である。新規POSTは従来どおりfalseとし、後続実行で有効化する。AC21は既存`active:false`を明記し、第1段階の不一致後に有効化PUTが0件であることを観測する。これは実装手段ではなく「危険な実行パラメータが保存されなかったscheduleを起動しない」というP0の順序保証である。 | Critical |
| 2 | 同上 | 63-66, 76 | **R8-2の「`template_id`は常にカタログ値」は、R3の「`template_id`をカタログへ書かない」と両立しない。** カタログが持つのは対象template名であり、API payloadの`template_id`は適用先で一意に解決した値である。出所を誤ると、存在しないcatalog fieldを読む実装またはid固定の実装を許す。effective desired stateを「`template_id`はカタログのtemplate名から当該APIで一意に解決したid」と直し、R1の5管理項目（論理項目）とAPI上の比較フィールドを区別する必要がある。 | High |
| 3 | 同上 | 75, 234-237 | **AC22のGivenでは、既発行PUTをレポートする要件を観測できない。** identity変更を「1件目のPUTの前」に発生させるため、検出対象が最初に処理されれば既発行PUTは必ず0件であり、Thenの「既に発行済みのPUTがあれば」は常に空でも合格できる。一方R8が明記する残余は、先行scheduleのPUT後に後続scheduleのidentity変化を検出した部分適用ケースである。処理順をfixtureで固定し、**1件目の安定したscheduleへのPUT成功後、2件目のidentityを変更して検出させる**Givenにし、レポートが1件目のPUTを具体的に記録すること、2件目以降のPOST/PUTが0件であることをThenで要求する必要がある。部分適用が起きた事実を隠さないという受入契約なので、test_planだけへ送れない。 | High |

## Suggestions

### 分類2: implementまたはtest_planへ送ってよいもの（6件）

第9節の既存6件は、引き続き記載された送り先へ移してよい。追加の分類2 findingは無い。

| # | 引継ぎ先 | 内容 | 判定 |
|---|---|---|---|
| 4 | implement | PUT round-trip、DB構造、19件`task_params`、deep equality、型保持/OQ7 | 後続可 |
| 5 | test_plan | AC15のreachable mockまたはURL判定unit test | 後続可 |
| 6 | test_plan | 結果へ影響しないACの3軸fixture表記統一 | 後続可 |
| 7 | Tester(初回quory) | OQ1の20/19とOQ3のAPI/SQLite突合 | 後続可 |
| 8 | implement | OQ5のtransaction/ETagと残余競合fixture | 後続可 |
| 9 | test_plan | OQ8の孤児行増加・冪等時非増加・cleanup別判断 | 後続可 |

## What Looks Good

- R8-2により、カタログ値と安全gate適用後のeffective desired stateを概念として分離した点は前回Finding #1を解消している。移行期間、接続先不許可、明示許可なしでは、既存`active:false`を正常に維持して理由を報告できる。
- AC4から`task_params`を非管理フィールドとする誤記が除かれ、管理5項目以外の保持を単一GETで観測する形になった。
- AC21はHTTP成功と保存値一致を区別し、APIによる未知keyの黙示破棄をnegative fixtureにした。Finding #1はこのACによって露呈した書き込み順序の欠陥であり、write-after-read自体の採用は妥当である。
- AC22はclosed-worldでidentity変化を検出した際の非ゼロ終了と残り書き込み中止を明記した。Finding #3は、部分適用レポートを実際に観測できる時系列への修正に限る。
- 移行期間とclosed-world、新規と既存、`true → false`と`false → true`、canonical本番URLとそれ以外の境界は明示されている。
- duplication/reuse: template reconcileの既存playbook・reportを再利用しながら、schedule固有の単一GET、管理対象、競合契約を分離している。指定資産の再利用方針に新たな欠落はない。
- security: token値の非記録、秘密候補と判定不能のpreflight停止、canonical URL allowlist、DELETE禁止、TLSを弱めない要件は維持されている。
- Reviewer定型観点: requirement段階のため多層エスケープとshell rc規約は対象なし。`--check`で評価されないPOST/PUT/write-after-read/有効化はACに現れているが、Finding #1の順序保証が必要である。判定不能を成功へ落とす無音化・例外吸収は要求されていない。

## 確認範囲

- 第10稿requirement全文、前回`2026-08-09_010_review_requirement_r9.md`、着手時のworktree status/diff
- R8/R8-2/R12/R13/R16/R16-2とAC3/AC6/AC15/AC21の`active`状態遷移およびAPI call順序
- R3/R8-2のtemplate名から`template_id`への解決契約
- R8のclosed-world部分適用残余とAC22のGiven/Thenが観測する時系列
- Semaphore System Context、Ansible test safety policy、既存`semaphore_templates` role/playbook/reportの接続箇所
- duplication/reuseおよびAnsible security観点

## 未確認事項

- Semaphore APIへのGETを含め、API呼出しは行っていない。本文の2.18.4実測値は今回再測定していない。
- Ansibleは実ホスト・decoy・syntax-checkのいずれも実行していない。
- 実装コード、mock方式、deep equality、`task_params` schema、競合注入手段は後続工程の確認対象である。
- commit、pushは行っていない。

## Verdict

**Request Changes** — 分類1は3件。特に、保存値検証より先に`active:true`を同じPUTで反映し得る点は、AC21が主張するfail-closedを満たさず、本番scheduleを意図せず起動し得るためrequirement確定前に修正が必要である。
