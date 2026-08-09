# Code Review: semaphore_schedules failure-path re-review 4

## Summary

3点のうち、`_020` Mediumとansy向けreport保存先はclosed。`_020` Highはschedule失敗時には閉じたが、report-onlyのUNREACHABLEでは同じextra-vars上書きによりrc 0へ倒れるためopen。新規の別findingは無い。

## Finding Status

| Item | Status |
|---|---|
| `_020` High #1（内部失敗factのextra-vars上書き） | **open** |
| `_020`でopenだったMedium #2（report UNREACHABLEが元のschedule失敗を置換） | **closed** |
| Tester §1（ansy接続ユーザーが既定report保存先へ書けない） | **closed** |

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `roles/semaphore_templates/tasks/main.yml` | 204 | **`ansible_failed_result is defined`はreport-onlyのUNREACHABLEを捕捉せず、前回Highのreport側が未解消。** `schedules_report.yml`はUNREACHABLEを`ignore_unreachable: true`で継続し、line 199以降の`set_fact`へ記録する。この状態は`rescue`を発火させないため、schedule処理自体が成功していれば最終taskで`ansible_failed_result`は未定義のままである。そこで`-e '{"semaphore_schedules_report_save_failed": false}'`がset_factを覆うと、line 205-207の3条件がすべてfalseになり、report保存不能なのにplayは成功終了する。同じ実行モデルのlocalhost fixtureで、copyが実際に`UNREACHABLE!`、recapが`ignored=1`となった後、記録set_factが実行されたにもかかわらず最終failがskipされ、rc 0を再現した。`ignore_unreachable`で得たregistered resultそのものなど、extra-varsでfalseへ固定できない値を最終条件に含める必要がある。 | High |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 1 | `roles/semaphore_templates/tests/task_flow/run_task_flow_tests.py` | 216 | Scenario Dは必ず元のfixture failureを先に発生させるため、`ansible_failed_result` fallbackだけで通過する。schedule処理成功 + report-only UNREACHABLE + report failure factをnative falseで固定、の組合せでrc非ゼロをassertする。 | Test gap |

## What Looks Good

- `_020` Highのschedule失敗枝は、native falseでrun failure factを固定しても`ansible_failed_result is defined`で非ゼロになる。既存Scenario Cで確認した。
- reportがUNREACHABLEでも元のschedule失敗は保持される。既存Scenario Dで、`UNREACHABLE!`・`ignored=1`・元失敗の識別文言・非ゼロrcを確認したため、前回Mediumはclosed。
- `semaphore_templates_report_dir`と`semaphore_schedules_report_dir`はいずれも`semaphore_target`で分岐し、quoryは従来の`reports_base_dir`配下、ansyはinventory上の接続ユーザー`ann`が所有できる絶対pathになる。構文検査は両targetで成功したため、Testerの環境findingはclosed。
- 4つのtask-flow scenarioはすべて成功した。ただし上記Suggestionsの組合せは含まれない。
- 定型観点: shell/command追加はなくrc規約・多層エスケープの新規論点は無い。check modeではreport書き込みを意図的に実行する既存分類を維持している。`ignore_unreachable`の例外吸収はCritical #1の枝以外では明示的な失敗へ戻される。
- 実ホスト、Semaphore API、Slackには未到達。

確認実績:

- `python3 roles/semaphore_templates/tests/task_flow/run_task_flow_tests.py`（local/remote tempを`/tmp`へ指定）— 4 scenarios, OK
- localhostのreport-only UNREACHABLE fixture + native false extra-var — copyは`UNREACHABLE!`、最終failはskip、rc 0を再現
- `ansible-playbook playbooks/semaphore_templates_setup.yml --syntax-check` — 成功
- 同 `--syntax-check -e semaphore_target=ansy` — 成功

## New Findings

無い。Critical Issues #1は`_020` High #1の未解消枝であり、新規の別findingではない。

## Verdict

Request Changes
