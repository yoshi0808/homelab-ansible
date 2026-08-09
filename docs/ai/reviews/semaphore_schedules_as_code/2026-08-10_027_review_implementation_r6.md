# Code Review: semaphore_schedules reserved-name guard re-review 6

## Summary

`_026` Critical #1はclosed。guardの判定は名前付き中間変数を持たず、extra-varsで評価結果を成功側へ差し替える構造は残っていない。指定範囲の新規指摘は無い。

## Critical Issues

無い。

## Suggestions

無い。

## What Looks Good

- `when:`は`lookup('varnames', ...)`の結果をallowlistリテラルで直接絞り込み、その場で長さを判定する。`vars:`、`set_fact`、`register`のいずれにも中間結果を保存しないため、前回利用できた上書き対象名が存在しない。
- 保護対象`semaphore_schedules_report_save_failed: false`と旧ヘルパー3名の上書きを同時に渡しても、production taskは対象名を列挙してrc 2で入口停止した。check modeでも同じ結果だった。
- 式中で外部から名前解決され得る`lookup`自体を上書きした試行は評価エラーでrc 2となり、guard skipや成功終了には倒れなかった。filter/test名とallowlistは式内のリテラルであり、extra-varsが差し替える名前付き値ではない。
- 通常の6つのrole default、Semaphore templateのsurvey変数`semaphore_templates_api_base_url` / `semaphore_templates_api_validate_certs`、正当な`semaphore_schedules_allow_activation=true`はproduction taskのlocalhost importをrc 0で通過した。
- `when:`と失敗message内のallowlist 6項目は一致している。設定として許可する既存6変数との照合にも差異は無い。
- task-flow 6シナリオはすべて成功し、Scenario Fが旧ヘルパー名によるguard迂回をnegative caseとして固定している。指定範囲で重大なtest gapは無い。
- 多層エスケープは単純な先頭regexだけで、対象内部名を意図どおり包含する。shell/command、独自rc規約、check modeで未評価になる分岐、機密値の表示、外部hostへのdelegate/lookupは追加されていない。
- 実ホスト、Semaphore API、Slackには未到達。

確認実績:

- production `schedules_validate_config.yml`のlocalhost import、保護対象 + 旧ヘルパー3名上書き — rc 2
- 同じ入力を`--check`で実行 — rc 2
- 同、通常survey変数 — rc 0
- 同、`semaphore_schedules_allow_activation=true` — rc 0
- 同、保護対象 + `lookup: []` — 評価失敗でrc 2（fail-closed）
- `python3 roles/semaphore_templates/tests/task_flow/run_task_flow_tests.py`（local/remote tempを`/tmp`へ指定）— 6 scenarios, OK
- `ansible-playbook playbooks/semaphore_templates_setup.yml --syntax-check` — 成功

## Verdict

Approve
