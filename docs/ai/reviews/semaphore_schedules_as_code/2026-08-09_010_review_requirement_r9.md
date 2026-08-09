# Code Review: Semaphore schedules as code requirement 9回目査読

## Summary

前回分類1のうち、公開可能性preflight、PUT直前GET、closed-worldでの残り書き込み停止は要件本文へ反映された。しかし管理5項目の「catalog値への完全一致」が、意図的にcatalogと異なる`active:false`を維持する安全gateと衝突している。また新設した2つのfail-closed分岐を識別するACが無い。したがって**分類1は2件**残り、分類2の6件は記載どおり後続へ送ってよい。

## Critical Issues

### 分類1: requirement段階で直す必要があるもの（2件）

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 75, 84-89, 143-161, 198-221 | **管理5項目を常にcatalog値で上書き・検証するR8/R16-2は、条件付き`active`の安全設計と両立しない。** catalogが`active:true`でも、新規POSTはR13によりfalse、移行期間・不許可URL・明示許可なし・競合時の既存scheduleもR12によりfalseを維持する。ところがR8は`active`を含む管理5項目をcatalog値で上書きし、R16-2はPOST/PUT直後に5項目すべてがcatalog値と完全一致しなければ非ゼロとするため、(a) gateを無視してtrueへするか、(b)安全にfalseを保って正常ケースを失敗させるかの二択になる。**書き込みpayloadとwrite-after-readの比較対象を「その実行のeffective desired state」へ分ける必要がある。** `name/template_id/cron/task_params`はcatalog値、`active`は新規ならfalse、既存のtrue→falseならcatalog false、false→trueはR12の4条件成立時だけtrue、それ以外はobserved falseとする。R16-2はこのeffective値との一致を検証し、catalogとの差は「有効化待ち/見送り」としてreportする。併せてAC4 Givenに残る「非管理フィールド(`task_params`等)」も、`task_params`が管理対象になった現契約へ直す。 | Critical |
| 2 | 同上 | 75, 88, 203-226 | **今回新設・変更したfail-closed分岐を、既存ACから識別できない。** R16-2の要点は「HTTP成功でもAPIが未知keyを捨てたら、直後GET不一致を検出して非ゼロ・有効化禁止」だが、AC18/AC19は受理される正常な`task_params`しか試さないため、write-after-read検証を実装しなくても通る。またR8のclosed-world identity競合は「残りの全POST/PUT中止・非ゼロ」だが、AC20は移行期間の1件skip・終了0・他更新継続だけである。未知key fixtureのPOST/PUT成功→GET不一致→非ゼロ・active false、およびclosed-worldのpreflight後identity変更→残り書き込み中止・非ゼロをACへ追加する必要がある。これはtest fixtureの具体化ではなく、相反する実装を受入段階で落とすためのrequirement上の観測契約である。 | High |

## Suggestions

### 分類2: implementまたはtest_planへ送ってよいもの（6件）

第9節に、前回分類した6件が送り先とともに全て記載されている。追加の分類2 findingは無い。

| # | 引継ぎ先 | 内容 | 判定 |
|---|---|---|---|
| 3 | implement | PUT round-trip、DB構造、19件`task_params`、deep equality、型保持/OQ7 | 後続可 |
| 4 | test_plan | AC15のreachable mockまたはURL判定unit test | 後続可 |
| 5 | test_plan | 結果へ影響しないACの3軸fixture表記統一 | 後続可 |
| 6 | Tester(初回quory) | OQ1の20/19とOQ3のAPI/SQLite突合 | 後続可 |
| 7 | implement | OQ5のtransaction/ETagと残余競合fixture | 後続可 |
| 8 | test_plan | OQ8の孤児行増加・冪等時非増加・cleanup別判断 | 後続可 |

## What Looks Good

- R9はopaque `task_params`を公開repoへ置く前の秘密候補検査をpreflightへ入れ、判定不能も非ゼロへ倒した。既存19件が公開可能な値だけであるという実測も記録した。
- R8はPUT直前の単一GETを必須化し、identity変化時の挙動を移行期間とclosed-worldで分離した。移行中の限定skipとclosed-worldの残り全書き込み停止はフェーズ保証と一致する。
- R19、AC17の管理項目数は5へ更新され、差分schemaも5項目前提になった。Finding #1は`active`のeffective値とAC4の残存表現だけを扱う。
- R16-2は「HTTP write成功」と「保存値一致」を分け、未知keyの黙示破棄を成功扱いしないfail-closedな方針を定めた。Finding #2はその観測不足だけを扱う。
- 第9節は分類2の6件をimplement/test_plan/Testerへ明示的に割り当て、requirement確定と後続検証を混同しない形になっている。
- `run_at`はDB read-only観測で既存19件に失われる値が無いことを確定済みであり、requirement段階のblockerではない。
- duplication/reuse: template側のmerge概念を再利用しつつ、schedule固有の単一GET、管理5項目、write-after-read、phase raceを独立契約にしている。
- security: secret候補/判定不能のpreflight停止、canonical本番URL allowlist、token非記録、TLS非弱化、DELETE禁止が要件化されている。
- Reviewer定型観点: requirement段階のため多層エスケープとshell rc規約は対象なし。`--check`で評価されないPOST/full PUT/write-after-read/有効化分岐はAC群に割り当てられているが、Finding #2のnegative ACが必要である。preflightとwrite-after-readは非ゼロ、有効化見送りは理由付きreportであり、無音の例外吸収を避ける設計である。

## 確認範囲

- 第9稿requirement全文、前回`2026-08-09_009_review_requirement_r8.md`、着手時のworktree status/diff
- 前回分類1の3件と、R8/R9/R16-2/R19、AC4/AC17-AC20、第9節の対応を突合
- migration/closed-world、new/update、catalog active/observed active、許可/不許可をeffective stateとして状態遷移確認
- 既存playbookのcheck-mode-native marker、read/reconcile/report/apply順序、Semaphore System Context、Ansible test safety policy
- duplication/reuseおよびAnsible security観点。実装固有のmodule引数、`no_log`、deep equality、mock方式は後続レビュー対象
- Coordinatorのansy API/DB実測は記録を読んだがReviewer自身では再実行していない。Semaphore APIアクセス、Ansible実行、commit、pushは未実施

## 未確認事項

- 既存19件の`task_params`公開可能性とAPI/DB実測はReviewerが独立再実行していない。
- 第9節のOQ1/OQ3/OQ5/OQ7/OQ8とtest fixture詳細は、分類2として後続確認が必要である。
- effective desired stateの実装表現とnegative fixtureは、Finding #1/#2反映後にImplementer/Testerが具体化する。

## Verdict

Request Changes — 分類1の2件が残る。これらを反映し、分類1が0件になればrequirement確定として実装へ進める。
