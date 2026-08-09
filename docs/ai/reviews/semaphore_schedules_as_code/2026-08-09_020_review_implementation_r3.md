# Code Review: semaphore_schedules failure-path re-review 3

## Summary

`_019` High #1はclosed。Medium #2は通常のFAILEDでは閉じたが、report taskがUNREACHABLEになるとrescueされず元失敗を保持できないためopenと判定する。さらに、再送出条件に使う新しいfactをextra-varsのnative `false`で固定すると、schedule失敗がrc 0へ吸収されるHighの新規findingがある。

## Finding Status

| Previous finding | Status | Evidence |
|---|---|---|
| `_019` High #1 | closed | inner rescueは生のmessageを表示せず、`no_log: true`のset_factでtoken scrub済みfactだけを作る。reportと最終failはいずれもこのfactを読む。task-flow scenario Aを実行し、起点taskのAnsible bannerより後にsentinelが残らず、JSONにもscrub済みmessageだけが入ることを確認した。起点task自身の`[ERROR]` bannerはrescue前に出るansible-coreの既存挙動であり、今回追加された経路ではない。 |
| `_019` Medium #2 | open | report保存が通常のFAILEDを返すscenario Bでは、独立factへ保存して元失敗と合成できる。しかしAnsibleのblock `rescue`はUNREACHABLEを捕捉しない。ローカル実行でreportのcopy taskがremote temporary directoryを作れずUNREACHABLEになった場合、line 136のrescueとline 147の最終合成taskへ到達せず終了することを確認した。この場合、後発のreport到達不能が元のschedule失敗を再び置き換える。 |

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `roles/semaphore_templates/tasks/main.yml` | 121 | **失敗判定factをextra-varsでnative `false`に固定すると、実際のschedule失敗が成功へ吸収される。** rescueは`set_fact: semaphore_schedules_run_failed: true`、report rescueは`semaphore_schedules_report_save_failed: true`を設定するが、extra-varsはset_factより優先される。`-e '{"semaphore_schedules_run_failed": false}'`があるとline 155/164はfalseを読み、report保存が成功した場合line 147のfailはskipされる。同じ構造のtask-flow fixtureへ`-e '{"fixture_run_failed": false}'`を渡し、起点taskがFAILED・rescue済みであるにもかかわらず最終failがskip、recap `failed=0`、process rc 0を再現した。report側factも同様に抑止できる。前回のflag修正で確認したextra-vars優先順位と同じ欠陥クラスであり、「失敗が成功へ吸収される経路を作らない」という今回の主眼に反する。外部から上書き可能な一般変数の真偽値だけで再送出を決めない構造へ変更するか、少なくともreserved internal変数の外部定義をschedule blockより前の捕捉されないgateで拒否する必要がある。 | High |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 1 | `roles/semaphore_templates/tests/task_flow/run_task_flow_tests.py` | 104 | native falseのextra-varで失敗factを固定するnegative caseを追加し、起点failure後のrcが必ず非ゼロであることをassertする。 | Test gap |
| 2 | `roles/semaphore_templates/tests/task_flow/run_task_flow_tests.py` | 137 | report taskがFAILEDだけでなくUNREACHABLEになったケースも固定し、少なくとも元failureの識別情報が失われないことをassertする。 | Ansible correctness / test gap |

## What Looks Good

- schedule failureと通常のreport-save failureを別factへscrubして保持し、両方がある場合に1つの最終failへ合成する通常経路は成立する。
- schedule failureだけ、report failureだけ、両方、どちらも無し、の通常FAILEDベースの分岐では、最終taskの条件により失敗が無条件に成功化される枝は見当たらない。
- report JSONは生の`ansible_failed_result`を直接読まず、scrub済みfactだけを保存する。
- task-flowテストは、sandbox用に`ANSIBLE_LOCAL_TEMP`と`ANSIBLE_REMOTE_TEMP`を`/tmp`へ向けた状態で2シナリオとも成功した。
- 定型観点: shell/commandとrc規約の追加論点は無い。check-mode分岐は今回の範囲外。例外吸収について、extra-vars優先順位による明示的なrc 0経路をCritical Issues #1、UNREACHABLEがrescue対象外である経路をopenのMedium #2とした。

確認実績:

- `ANSIBLE_LOCAL_TEMP=/tmp/... ANSIBLE_REMOTE_TEMP=/tmp/... python3 roles/semaphore_templates/tests/task_flow/run_task_flow_tests.py` — 2 scenarios, OK
- 同fixtureへnative falseのfailure factをextra-varで渡す追加実行 — 起点task FAILED後、最終fail skipped、rc 0を再現
- `ansible-playbook playbooks/semaphore_templates_setup.yml --syntax-check` — 成功
- 実ホスト、Semaphore API、Slackには未到達。並行Testerの状態変化は観測していない

## Verdict

Request Changes
