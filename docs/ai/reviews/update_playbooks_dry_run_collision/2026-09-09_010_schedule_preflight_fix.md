# 実装修正: schedule operation keyのpreflight許可契約

作成: 2026-09-09 / Implementer

## 原因

commit `ba98063`はschedule catalogの`environment`へ
`ubuntu_vm_full_upgrade_operation`と`prometheus_update_check_operation`を追加したが、
同じ値を消費する`semaphore_schedules.py`のclosed-world allowlistへ両keyを追加して
いなかった。このためjob #1027はtemplate 5件の差分検出後、schedule preflightで
両keyを未知として拒否した。preflightは書込前に停止したためAPI変更は発生していない。

## 修正

- `task_params.environment`へ両namespaced keyを追加した。
- Ubuntuは`inspect|apply`、Prometheusは`inspect|update|rollback`だけを許可し、
  文字列であってもenum外の値は拒否する。
- Semaphore native `task_params.params`のallowlistは既存の
  `force_renew|dry_run|debug_level`だけに維持した。operation keyをnative paramsへ
  混入しても拒否するため、operation軸とnative check軸は交差しない。
- 既存primitive値型、未知top-level/nested key拒否、値を診断へ出さない契約、
  schedule/template identity、catalogは変更していない。
- 診断の許可key一覧をenvironmentとparamsそれぞれの実際の正本へ揃えた。

## 回帰テスト

`scripts/tests/semaphore_schedules/test_operation_environment.py`を追加した。

1. 両operation keyの全許容enum値がpreflightを通る。
2. 両keyの未知operationが値を診断へ露出せず拒否される。
3. operation keyをnative `params`へ置くと未知keyとして拒否される。
4. job #1027相当のUbuntu/Prometheus 2 scheduleがclosed-world preflightを通り、
   既存IDのまま`task_params`だけのchangedとしてdiffされる（new 0件）。
5. 既存の未知key拒否・旧`force_renew|dry_run|debug_level` fixtureを含む全suiteを通す。

## 検証結果

| コマンド | rc | 結果 |
|---|---:|---|
| `python3 scripts/tests/semaphore_schedules/run-tests.py` | 0 | 97 tests OK（新規4 testsを含む） |
| `python3 -m py_compile roles/semaphore_templates/filter_plugins/semaphore_schedules.py scripts/tests/semaphore_schedules/test_operation_environment.py` | 0 | Python構文OK |
| `python3 roles/semaphore_templates/tests/task_flow/run_task_flow_tests.py` | 0 | 既存6 scenarios OK |
| `python3 scripts/check-doc-consistency.py` | 0 | 3 checks OK |
| `git diff --check` | 0 | whitespace errorなし |

## 未検証事項

- quory / 実Semaphore APIでのpreflight、diff、reconcile再実行は未実施。
- 実template / schedule readback、通常inspection、Slack通知は未実施。
- 実ホスト、quory、API、Slackへは触れておらず、commit / pushも行っていない。
- Incident本文はCoordinator管理のため編集していない。
