# Code Review: Semaphore schedules as code requirement 7回目査読

## Summary

対象版ansyでの実測により、単一GETをmerge元とするfull round-tripが`task_params`保持に必要だという前稿Criticalの技術的不確実性は解消した。フェーズgateとcanonical本番URLのallowlistも要件・ACへ反映されている。一方、その実測で`task_params`が定期実行の安全性を変えることが判明したのに、R1は依然4項目だけを正本とし、R8は`task_params`を非管理のまま保存するだけである。この状態ではリポジトリがschedule実行内容の正本にならず、新規scheduleの安全な作成も定義できない。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 14-15, 53-55, 63, 75, 98-112, 139-147 | **`task_params`に実行内容を変える安全上の値があると実測したのに、カタログの正本対象から除外している。** R1の4項目だけでは、既存scheduleの`dry_run=true`、`force_renew=false`、`debug_level`をリポジトリから読めず、UIで変更されてもreconcileはraw値をそのまま保持するため差分にも復元対象にもならない。Operatorがrepoを正本として答えるユーザーストーリーを満たさず、closed-worldで作る新規scheduleには必要な`task_params`をcatalogから与える手段も無い。特にfull-upgrade系の`dry_run`はcronやactiveと同じく定期実行の危険度を変えるため、「壊さずに正本化」の範囲外にはできない。R1へ型付き`task_params`を追加し、ホスト間で変わる値があれば名前解決規則を定義し、既存19件の値をcatalogへ転記する必要がある。ACには ①UIで`task_params`を変えるとcatalog値へ戻る ②新規作成時にcatalog値が入る ③冪等時に維持される、を含める。もし意図的に非管理とするなら、ゴールとユーザーストーリーを「時刻と有効状態だけの正本」へ縮小し、`task_params`を持つtemplateの新規schedule作成を禁止する必要がある。 | Critical |
| 2 | 同上 | 47-49, 75, 109, 224 | **`run_at`をAPIで観測できないことを、そのまま「壊れていないことを保証しない」にしており、既存19件を壊さないという査読主眼を満たしていない。** API requestへ含まれないことは、PUT handlerがDB上の次回実行時刻を保持・再計算・消去のどれにするかを示さない。通常のUI更新と同じendpointであることは安全の傍証にはなるが、受入観測ではない。ansy DBのread-only比較、または制御したprobe scheduleの次回起動観測など、API以外の観測点で「cron変更時は期待どおり再計算され、非cron更新時は不要な欠落・重複を生まない」ことを対象版で確定する。観測手段が無いなら、少なくとも初回quory適用の停止条件と段階観測を明記し、単なる非保証として閉じない。 | High |
| 3 | 同上 | 33, 47, 75-76, 88, 144-147 | **非管理fieldを保持するmerge元の取得時点が定義されておらず、UI編集とのlost updateが残る。** 既存task順序はread/reconcile/report/applyであり、preflight時の単一GET rawをapplyまで保持してPUTすると、その間にUIで変更された`task_params`を古い値で上書きできる。R16の再GETは有効化直前のschedule集合だけで、通常のcron/template/`true → false`更新を守らない。各PUTの直前に対象scheduleを単一GETし、その最新rawへcatalog管理項目をmergeすることをR8へ明記する。さらにpreflight snapshotからidentity/nameが変わった場合は当該PUTを見送るか停止し、ACでpreflight後に`task_params`を変更しても最新値を失わないことを観測する必要がある。ETagが無いためGET後の残余競合は残るが、窓を実装上最小化できる。 | High |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 4 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 199-202 | AC15の「未知URL」をfull playbookで試すなら、R11の`GET /api/info`やschedule GETへ正常応答するreachable mockであることを明記する。到達不能URLではallowlist判定より先に接続失敗し、要求する終了コード0を観測できない。URL判定をfilter/pluginのunit testとして分離する方法でもよい。 | test fixture / Medium |
| 5 | 同上 | 127, 134-137, 169-172, 179-192 | 文書内規約どおり、AC2/AC9/AC11/AC13にも有効化許可の前提を明記する。結果へ影響しないfixtureでも、全ACが同じ3軸を自己完結して示すという規約と現物を一致させる。 | acceptance precision / Medium |

## What Looks Good

- 6項目PUTで実データの`task_params`が消えること、単一GET rawのfull PUTで復元・一致することをansyの対象版で確認し、R8を推測から実測契約へ変えた。公式例を安全根拠にしなかった点は重要である。
- 一覧GETは`task_params`を欠き`tpl_name`を含むためmerge元にしない、単一GETだけを使う、という区別は明確で、誤った再利用を防ぐ。
- R12は`false → true`の4条件へclosed-worldを明記し、AC14と要件本文の不一致を解消した。
- R15はcanonical本番URLだけを許すallowlist型になり、ansy/別名/未知URLをfail-closedにする。AC15も明示許可ありのnegative casesと本番URLのpositive caseを区別している。
- AC4は単一GETと非空`task_params` fixtureを指定し、単なるid維持ではなく非管理field保持を直接観測する。
- renameは移行期間の未実在名とclosed-worldの管理外検出の双方で拒否され、フェーズ別の管理外処理も一貫している。
- duplication/reuse: template側のmergeという抽象だけを再利用し、schedule固有の一覧/単一GET差を6.5で分離した。Finding #3の取得時点を除き、endpoint差を無理に共通化していない。
- security: token、TLS検証弱化、DELETE、shell/command変数展開は要求していない。`task_params`の黙示的消去が危険操作へ変わる具体的因果を要件内に残した。
- Reviewer定型観点: requirement段階のため多層エスケープとshell rc規約は対象なし。`--check`で評価されない分岐はPOST、full PUT、`true → false`、条件付き`false → true`でありAC3-AC6/AC12/AC14-AC17が扱うが、task_paramsの正本化と直前mergeを追加する必要がある。preflight errorは非ゼロ、有効化見送りは理由付きreportであり、「該当なし」と「判定不能」を無音の成功へ落としていない。

## 確認範囲

- 第7稿requirement全文、前回`2026-08-09_007_review_requirement_r6.md`、着手時のworktree status/diff
- 6.5の測定結果とR1/R8/R12/R15、AC4/AC14/AC15、OQ6/OQ7の相互整合
- `playbooks/semaphore_templates_setup.yml`のcheck-mode-native marker、`hosts: quory`固定とAPI base URL override
- `roles/semaphore_templates/tasks/main.yml`のread/reconcile/report/apply順序と、template側applyのget-then-merge-then-send形
- `docs/ai/context/system/semaphore.md`のUI状態がGit外で変化し得ること、ansy/quoryの役割分離
- `docs/ai/policies/ansible_test_safety_policy.md`のcheck-mode-native要件
- duplication/reuseおよびAnsible security観点。requirement査読のため、未実装schedule taskのmodule引数、secretログ、権限、入力サニタイズは未判定
- Coordinatorが記録したansy書き込み実測は、今回の制限に従いReviewer自身では再実行していない。Semaphore APIアクセス、Ansible実行、commit、pushは未実施

## 未確認事項

- ansyでの6項目PUT、full PUT、復元、19件の`task_params`内容は、6.5の記録を読んだがReviewerは独立再実行していない。
- OQ1の20/19不一致とOQ3のquory API/SQLite突合は未解決である。
- schedule PUTがDB上の`run_at`へ与える影響、Semaphore APIのtransaction/ETagの有無は未確認である。
- `task_params`の型付き構造全体と、ansy/quory間で同じcatalog値をそのまま使えるかは未確認である。
- canonical本番URL以外のAC15 fixtureをfull playbookで実行できるreachable mockの有無は未確認である。

## Verdict

Request Changes
