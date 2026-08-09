# Code Review: semaphore_schedules reserved-name guard re-review 5

## Summary

`_023` Critical #1はopen。予約済みのschedule内部名そのものは拒否するが、guardの判定用ヘルパー変数をextra-varsで上書きするとguardを迂回でき、report-only UNREACHABLEをrc 0へ吸収する元の経路が復活する。正当な既定値およびSemaphore templateのsurvey変数は誤拒否しないことを確認した。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `roles/semaphore_templates/tasks/schedules_validate_config.yml` | 83 | **guard自身の判定値をextra-varsで空に固定できるため、予約名検査を迂回できる。** task-level `vars`もextra-varsより優先順位が低い。`-e '{"semaphore_schedules_report_save_failed": false, "_reserved_name_guard_unexpected": []}'`をproductionのtask fileへ渡すと、line 108の`when`は外部の空listを読み、guardがskip、後続taskまでrc 0で到達した。`_reserved_name_guard_observed: []`またはallowlistへ攻撃対象名を加える上書きでも同じ判定を汚せる。さらにstructural fixtureへ同じ迂回を重ねると、schedule相当処理成功、report writeは実際に`UNREACHABLE!`、記録用set_fact実行、最終fail skip、rc 0を再現した。したがって「extra-varsは名前を未定義にできない」という前提自体は正しいが、その存在検査の入力・中間結果が外部上書き可能なため `_023` の成功吸収経路を閉じていない。外部から名前で参照できるtask varsへ判定を保存せず、上書き不能な評価としてfail条件を構成する必要がある。 | High |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 1 | `roles/semaphore_templates/tests/task_flow/run_task_flow_tests.py` | 275 | Scenario Eへguardの判定用ヘルパー変数をnativeな空listで固定するnegative caseを追加し、guardが入口で非ゼロ停止することをassertする。現行Scenario Eは保護対象のfailure factだけを上書きするため、guard自身の迂回を検出できない。 | Test gap |

## What Looks Good

- 保護対象だけを事前定義した場合、production guardは対象名を列挙してrc 2で入口停止する。
- 6つのrole default設定変数はallowlistに一致し、通常のvalidationはrc 0で完走する。
- Semaphore templateのsurveyが渡す`semaphore_templates_api_base_url`と`semaphore_templates_api_validate_certs`は`(_)?semaphore_schedules_*`に一致せず、同じproduction task fixtureで誤停止しないことを確認した。
- `lookup('varnames', '^_?semaphore_schedules_.*')`のpatternは対象の先頭prefixを意図どおり列挙する。多層エスケープ、shell/command、独自rc規約、check-mode固有分岐の追加論点は無い。
- 既存task-flow 5シナリオとplaybookのsyntax-checkは成功した。ただし上記のguard-helper上書きケースは未収録。
- 実ホスト、Semaphore API、Slackには未到達。

確認実績:

- production `schedules_validate_config.yml`のlocalhost import、通常survey変数あり — rc 0
- 同、`semaphore_schedules_report_save_failed: false` — guardでrc 2
- 同、上記に`_reserved_name_guard_unexpected: []`を追加 — guard skip、rc 0
- structural report-only UNREACHABLE fixtureへ同じguard迂回を追加 — `UNREACHABLE!` / `ignored=1`、最終fail skip、rc 0
- `python3 roles/semaphore_templates/tests/task_flow/run_task_flow_tests.py`（local/remote tempを`/tmp`へ指定）— 5 scenarios, OK
- `ansible-playbook playbooks/semaphore_templates_setup.yml --syntax-check` — 成功

## Verdict

Request Changes
