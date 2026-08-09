# Code Review: Semaphore schedules as code requirement 8回目査読

## Summary

前回の`task_params`正本化、`run_at`、PUT直前GETは設計方針として反映され、requirementは収束に近い。残課題を工程で分けると、**requirement確定前に直すものは3件**、**implement/test_planへ送ってよいものは6件**である。前者は管理対象の自己矛盾、公開repoへ置くopaque payloadのfail-closed契約、closed-world競合時の停止範囲であり、実装者の判断へ委ねると安全挙動が分岐する。

## Critical Issues

### 分類1: requirement段階で直す必要があるもの（3件）

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 63, 75, 147-150, 227-230 | **`task_params`を5番目の管理項目にした一方、更新契約とACが旧「管理4項目」のままで相反する。** R8はraw objectへ「管理4項目だけ」を上書きするため、字義どおりならcatalogの`task_params`をPUTへ反映しない。AC4も`task_params`を非管理fieldとして実行前値の保持対象にし、AC17も管理4項目以外を保持するとしており、catalog値へ戻すAC18と両立しない。R8を「管理5項目を上書き」、AC4/AC17を「`task_params`を除く非管理fieldの保持」へ改め、diff/report schemaも5項目を前提にする必要がある。 | Critical |
| 2 | 同上 | 63, 76, 106, 113, 212-220, 241-243 | **opaqueな`task_params`を正本へ採用するためのfail-closedな受入契約が不足する。** 第一にrepoは公開前提なのに、APIから取得したopaque blobを19件そのまま転記する前のsecret/password/token等の検査・停止条件が無い。第二にAPIは未知keyを黙って捨てるため、将来catalogへ誤ったkeyを追加するとPOST/PUTは成功してもGET値がcatalogと一致せず、PUTごとに孤児行を作り得る。新規scheduleはfalseで作られるが、次回applyで不完全な`task_params`のまま有効化できる条件も残る。R9へ「catalogの`task_params`は公開可能な値だけであることを確認し、判定不能または秘密候補があれば停止」を加え、POST/PUT直後の単一GETで管理5項目の完全一致を必須にし、不一致なら非ゼロ・有効化禁止とする。schema全体の解明は後続でよいが、未知/正規化された値を成功扱いしない方針はrequirementで決める必要がある。 | Critical |
| 3 | 同上 | 43-47, 75, 88, 94-95, 222-225 | **PUT直前にidentity変化を検出した後の挙動が全フェーズ共通で「その1件だけ見送り・他を更新」となり、closed-worldのfail-closed保証と衝突する。** 移行期間ならAC20の限定skipはフェーズ表と一致する。しかしclosed-worldでname/idが変わったことは、preflight後に管理外または置換scheduleが生じた証拠であり、R18の「管理外なら全書き込み停止」と同じ安全側へ倒すべきである。R8をフェーズ別にし、移行期間は当該1件skip+継続、closed-worldは残りのPOST/PUTを停止して非ゼロ・再preflight要求と定義する。既に発行済みのPUTをrollbackできない残余は明記し、closed-world版の競合ACを追加する必要がある。 | High |

## Suggestions

### 分類2: implementまたはtest_planへ送ってよいもの（6件）

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 4 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 98-115, 241 | 6.5のPUT round-trip、DB構造、既存19件の`task_params`を後続が再現し、YAML/JSONのdeep equalityと型保持をfixture化する。OQ7のschema全体調査は、Finding #2の「不一致はfail-closed」が要件化されればimplement/test_planへ送ってよい。 | implementation verification |
| 5 | 同上 | 202-205 | AC15の別名・未知URLは、正常な`/api/info`とschedule GETを返すreachable mock、またはURL判定filter/pluginのunit testとして具体化する。到達不能URLでは接続失敗が先に起きるため、allowlist判定そのものを観測できない。 | test fixture |
| 6 | 同上 | 130, 137-140, 172-175, 182-195 | 結果へ影響しないAC2/AC9/AC11/AC13にも、文書内規約どおり有効化許可の既定fixtureを補う。これは設計分岐を増やさずtest_planで統一できる。 | acceptance precision |
| 7 | 同上 | 236, 238 | OQ1の20/19不一致とOQ3のquory API/SQLite突合は、初回quory read-only preflightの観測項目としてTesterへ引き継ぐ。現在の19件採用は、列挙とRestore DBの2観測が一致しており実装設計を分岐させない。 | production observation |
| 8 | 同上 | 47, 88, 240 | OQ5のtransaction/ETag有無と、GET後からPUTまでの残余競合を実装調査・競合fixtureへ送る。requirementは「無い前提で窓を最小化し、残余をreport」と既に安全側の挙動を決めている。 | concurrency verification |
| 9 | 同上 | 113-115, 243 | OQ8の孤児`task_params`行は、差分があるPUTだけで増えること、idempotent runでは増えないこと、増加件数をDB read-onlyで観測するテストを置く。cleanupの実装可否・保持期間は別の運用判断として後続へ送ってよく、本件のreconcileへ暗黙のDB削除を加えない。 | data lifecycle |

## What Looks Good

- `task_params`をscheduleの実行内容を決める管理対象へ昇格し、UI drift、new、idempotencyのAC18/AC19/AC5を置いた判断は前回Criticalの本質を反映している。Finding #1/#2はその契約を実装可能な形へ閉じるためのものに限定した。
- DB read-only観測で既存19件の`run_at=NULL`、`type`空を確認したため、前回Highの「見えない値を非保証にする」問題は本件の母集団について解消した。
- R8は各PUT直前の単一GETをmerge元にし、preflight rawの持ち回りを禁止した。移行期間のidentity raceはAC20で直接観測する。
- R12のclosed-world gate、R15のcanonical本番URL allowlist、R18のフェーズ別管理外処理、rename全面禁止は一貫している。
- 6項目PUTが`task_params`を消す具体的な本番事故経路を対象版で実測し、一覧GETと単一GETのpayload差も設計へ反映した。
- duplication/reuse: template側のmerge概念は再利用しつつ、schedule固有の単一GET、opaque `task_params`、直前再取得を独立契約としている。重複抽象化を急いでendpoint差を隠していない。
- security: token、TLS弱化、DELETE、shell/command変数展開は要求していない。公開repoへopaque `task_params`を置く際の不足だけをFinding #2で切り出した。
- Reviewer定型観点: requirement段階のため多層エスケープとshell rc規約は対象なし。`--check`で評価されない分岐はPOST、full PUT、管理5項目更新、条件付き有効化でありAC3-AC6/AC12/AC14-AC20が扱うが、Finding #1/#2の更新後検証が必要である。preflight失敗とwrite-after-read不一致はfail-closed、有効化見送りは理由付きreportとすることで、無音の例外吸収を避けられる。

## 確認範囲

- 第8稿requirement全文、前回`2026-08-09_008_review_requirement_r7.md`、着手時のworktree status/diff
- R1/R8/R9/R12/R15/R18とAC4/AC5/AC15/AC18-AC20を、管理項目数、opaque payload、migration/closed-world競合、new/update/activationとして照合
- 6.5のAPI/DB測定記録とOQ1/OQ3/OQ5/OQ7/OQ8の工程振り分け
- `playbooks/semaphore_templates_setup.yml`のcheck-mode-native marker、API base URL override、既存roleのread/reconcile/report/apply順序
- `docs/ai/context/system/semaphore.md`の公開情報・UI外部変更・ansy/quory境界、`docs/ai/policies/ansible_test_safety_policy.md`のcheck-mode-native要件
- duplication/reuseおよびAnsible security観点。未実装taskのmodule引数、`no_log`、filter実装、deep equalityは後続レビュー対象
- Coordinatorのansy API/DB実測は記録を読んだがReviewer自身では再実行していない。Semaphore APIアクセス、Ansible実行、commit、pushは未実施

## 未確認事項

- 既存19件のopaque `task_params`が公開repoへ置ける内容だけであることは未確認である。
- ansyでのPUT/復元、DBの`run_at`/孤児行、19件の`task_params`はReviewerが独立再実行していない。
- OQ1/OQ3/OQ5/OQ7/OQ8は分類2として後続確認が必要である。
- closed-worldのpreflight後identity変更を再現するfixtureと、AC15のreachable mock/unit経路は未確定である。

## Verdict

Request Changes — 分類1の3件を直した時点でrequirementを確定し、分類2の6件は明示的にimplement/test_planへ引き継いでよい。
