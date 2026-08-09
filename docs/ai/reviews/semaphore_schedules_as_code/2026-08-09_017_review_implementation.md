# Code Review: semaphore_schedules_as_code implementation

## Summary

R8/R8-2/R8-3 と R15 の安全境界を破る blocking finding が2件あり、現状は適用不可。純Pythonの70テストとplaybookのsyntax-checkは通るが、task層の状態遷移・失敗経路・check/apply差を通すテストが無く、AC1〜AC23の成立を示せていない。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `roles/semaphore_templates/tasks/schedules_apply_stage1_item.yml` | 66 | **PUT直前GETより古い `active` をstage 1 payloadへ戻す。** `item.after` は `schedules_diff.yml:45-51` の早い単一GETから算出され、PUT直前のfresh GETはidentity確認とmerge元にしか使われない。例えばカタログ`active: true`、初回GET`active: true`、cron差分ありのscheduleを、UIがPUT直前に`active: false`へ変えると、line 73が古い`item.after.active: true`をfresh rawへ上書きし、R12の4条件を経ずstage 1で再有効化する。R8のfresh get-then-merge、R8-2の「既存は観測値のまま」、R8-3の「第1段階では有効化しない」、AC20に反する。PUT直前GETを入力にstage 1 desiredを再計算し、その値をpayload・直後検証・stage2 precheck用の検証済み状態へ一貫して渡す必要がある。 | Critical |
| 2 | `roles/semaphore_templates/filter_plugins/semaphore_schedules.py` | 619 | **extra-varsの文字列を真偽値として無検証に評価するため、`-e semaphore_schedules_allow_activation=false` が有効化許可になる。** `ansible-playbook -e key=value`の値は文字列であり、非空文字列`"false"`はline 627の`if not allow_flag`を通過する。ローカルで同関数へ`allow_flag="false"`を渡すと`allowed: True`を再現した。`closed_world`も同じく非空文字列をtrue扱いする。R12条件①/③、R15の既定不許可・明示許可に反し、条件が揃えば意図せず`false -> true`を発行する。task入口で両設定を厳密に型検証・正規化し、不明値を停止させる必要がある。 | Critical |
| 3 | `roles/semaphore_templates/tasks/main.yml` | 72 | **失敗時にscheduleレポートへ到達しない。** stage1/stage2またはpreflightがfailするとblockの残り(line 80-81)はskipされrescueへ移る。したがって1件目のPUT成功後に2件目のidentity driftで止まるAC22で、`semaphore_schedules_stage1_written`はメモリ上にあってもJSONレポートへ保存されない。closed-worldの管理外preflight失敗でもR18の管理外レポートが保存されない。R8が求める既適用分の残余記録、R18、AC22を満たすよう、失敗経路でも安全に生成できるレポートを保存した後、元の失敗を非ゼロで再送出する必要がある。 | High |
| 4 | `roles/semaphore_templates/defaults/main.yml` | 560 | **ansy向け既定token pathが既存token検査と両立せず、ゴールの「ansy/quory双方へ反映」を満たせない。** ansyでは`~/.semaphore-api-token-ansy`を導出する一方、`tasks/token.yml:19-22`はroot所有0600以外を拒否し、同defaultsの既存コメント(`:553-556`)もこのansyファイルはrole経由のroot所有チェックを通らないと明記している。さらに`become: true`下の`~`は対象ユーザーを曖昧にする。ansyで実在するtokenの絶対pathと所有権契約を確定し、秘密保護を弱めず両対象でtoken preflightが成立するよう揃える必要がある。 | High |
| 5 | `roles/semaphore_templates/tasks/main.yml` | 52 | **同一変更でtemplateとscheduleを追加するとcheckとapplyの前提が分岐する。** `--check`ではtemplate applyをskipした後、`schedules_read.yml:48-58`がAPI上のtemplateだけを再取得するため、新templateを指すscheduleはpreflightで0件解決となり失敗する。一方applyではtemplateを先に作成してから同じpreflightが通る。R10が明示する二段階順序と「`--check`とapplyで前提が分岐しない」に反し、追加予定templateを含むcheck時にも安全な差分/依存状態を表現できる接続が必要である。 | High |
| 6 | `roles/semaphore_templates/filter_plugins/semaphore_schedules.py` | 554 | **書き込み後検証が管理5項目だけで、非管理フィールドの保持を確認しない。** payload生成時にfresh rawの全フィールドを含めても、APIが`repository_id`、`delete_after_run`、`type`等を変更・破棄した場合、`semaphore_schedules_verify()`は成功を返す。AC4とAC17は直後GETで非管理フィールドも実行前と一致することを要求している。PUT直前rawと直後rawの非管理フィールド差も検証し、不一致を非ゼロにする必要がある。 | High |
| 7 | `roles/semaphore_templates/filter_plugins/semaphore_schedules.py` | 221 | **R9⑦の公開可否判定が未知値をfail-openする。** コメントは未認識キーもfindingにすると述べるが、実装は秘密らしい名前/値patternとIPv4だけを拒否し、`environment='{"opaque":"not-classifiable-value"}'`や`params.unexpected_control='arbitrary'`を問題なしで返すことをローカル再現した。これは「公開可能な値だけ」「判定できないときは停止」に反し、秘密や危険な実行パラメータが既知pattern外なら通る。実測済みの公開可能なキー/型を基準にしたallowlist、または同等に未知を拒否するrulesetが必要である。エラー本文には候補値そのものを載せず、検出pathだけを出すこと。 | High |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 1 | `scripts/tests/semaphore_schedules/` | 1 | localhostのstateful mock APIを使うtask層テストを追加し、少なくともAC1〜AC23を状態遷移へ対応付ける。最小の優先ケースは、(a) PUT直前の`active true -> false`競合でstage1が有効化しない、(b)文字列/不正型のphase・allow値がfail-closed、(c)1件目成功後の2件目失敗でも既適用分レポートが残りrc非ゼロ、(d)同一変更の新template+scheduleでcheck/applyの前提が一致、(e)APIが非管理フィールドを変えたら失敗、である。現行70テストはfilter単体だけで、`include_tasks`、block/rescue、check-mode gate、レポート到達性を通らない。 | Test gap |
| 2 | `scripts/tests/semaphore_schedules/test_preflight.py` | 200 | R9⑦に、既知patternへ一致しない未知キー/未知文字列を拒否するnegative caseと、エラーへ値を転載しないassertionを追加する。 | Security test gap |
| 3 | `scripts/tests/semaphore_schedules/test_strict_equal.py` | 1 | 自作subclassの回帰テストは有効だが、ansible-core 2.20.1のYAML由来`_AnsibleTaggedStr`とAPI JSON由来`str`を実際のtemplating境界で比較する小さなintegration testも固定する。Coordinatorの観測事実と現実装は整合しているが、現在のテストはAnsible自体を通らない。 | Test gap |

## What Looks Good

- `_strict_equal()`は数値kindだけを厳密化し、YAML由来のstr/dict wrapperとJSON由来の素の型を値一致として扱う。提示されたansible-core 2.20.1の観測事実と整合し、`task_params.environment`もJSON文字列のまま保持されている。
- schedule名重複、template名0/複数解決、cron、必須型、フェーズ別R6/R18を、書き込み前のpreflightへ集約している。DELETE経路は無い。
- stage2は集合再取得、canonical URL allowlist、個別fresh GET、管理4項目+`active: false`のprecheck、PUT直後GETの順に分離され、二段階書き込みの骨格は要件に沿う。
- API/tokenを扱うtaskは`no_log: true`を持ち、shell/commandや信頼できない`delegate_to`は追加されていない。lookupは固定文字列の時刻取得だけで、変数注入経路は見当たらない。
- `semaphore_schedules`用レポートはtemplateの`latest.json`と別directoryで、成功経路と`--check`では保存される。
- 重複・再利用観点では、requirementが指定した既存資産の再利用漏れは見当たらない。別roleのDLP実装との統合はrequirementで指定されていないため、それ自体はfindingにしていない。
- 定型観点: Jinja→YAMLの多層評価ではCritical #2の文字列真偽値を検出した。shell/command/grep/journalctl等を追加していないためrc規約の新規論点は無い。`--check`で評価されない書き込み分岐はimport単位でgateされているが、R10のcheck/apply前提差をHigh #5とした。rescueは失敗を成功へ吸収せず再送出する一方、レポートを無音で飛ばす問題をHigh #3とした。

確認実績:

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/tests/semaphore_schedules/run-tests.py -v` — 70 tests, OK
- `ansible-playbook playbooks/semaphore_templates_setup.yml --syntax-check` — 成功
- 同 `-e semaphore_target=ansy` — 成功
- 実ホスト、Semaphore API、Slackには未到達。apply/POST/PUTの実行は未実施。

残存する未確認事項:

- Semaphore 2.18.4が受理するcron grammarと、新規POSTに管理5項目+`project_id`以外の必須fieldがあるかは未確認。
- AC1〜AC23のtask層integration結果、ansy/quoryの実API round-trip、OQ1/OQ3/OQ5/OQ8は未確認。

## Verdict

Request Changes
