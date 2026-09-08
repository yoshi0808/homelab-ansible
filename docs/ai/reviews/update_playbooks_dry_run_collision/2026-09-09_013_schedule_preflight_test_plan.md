# test_plan: schedule operation key preflight修正

Tester / 2026-09-09
契約: `2026-09-09_010_schedule_preflight_fix.md`、`2026-09-09_011_schedule_preflight_review.md`、
`2026-09-09_012_schedule_preflight_rereview.md`（Verdict: Approve）、
`docs/ai/memory/incidents/2026-09-09_schedule_operation_keys_rejected.md`（状態: 解決済み）。

## 0. 前提確認

- 対象差分: `roles/semaphore_templates/filter_plugins/semaphore_schedules.py`、新規
  `scripts/tests/semaphore_schedules/test_operation_environment.py`、Incident、010〜012。
- 012 rereviewはApprove（Critical/Major/Minorなし）。残作業は実Semaphore配備後観測のみ。
- 本Testerは差分をコードで読み、Implementer/Reviewerの主張(97 tests、6 scenarios、doc/diff rc=0)を
  自分でも再実行して確かめる。加えてReviewerが行ったspot-check相当を独立に再現する。

## 1. 安全境界

- 実host、quory、Semaphore API、production Slackへは触れない。
- catalog reconcile、commit/pushは行わない。
- 検証は`roles/semaphore_templates/filter_plugins/semaphore_schedules.py`の公開関数
  （`semaphore_schedules_preflight`、`semaphore_schedules_diff`）をPythonから直接importし、
  fixtureデータのみで実行する（ネットワーク・ファイルシステムへの副作用なし）。

## 2. 検証項目

1. 既存回帰: `python3 scripts/tests/semaphore_schedules/run-tests.py`（97 tests）、
   `python3 roles/semaphore_templates/tests/task_flow/run_task_flow_tests.py`（6 scenarios）、
   `python3 -m py_compile`、`python3 scripts/check-doc-consistency.py`、`git diff --check`。
2. job #1027相当のUbuntu/Prometheus 2 scheduleが、`closed_world=True`のpublic preflightを
   通り(`errors=[]`, `unmanaged=[]`)、続くpublic diffで既存ID(40/41)の`changed`(`fields=['task_params']`)
   かつ`new=[]`となることを確認する(既存testの追試 + 独立再実行)。
3. 全正規enum値(`ubuntu_vm_full_upgrade_operation`: inspect/apply、
   `prometheus_update_check_operation`: inspect/update/rollback)がpreflightを通ることを確認する。
4. 独立spot-check(Reviewerの確認と同種だが自分で再現する):
   - cross-enum（一方のkeyへ他方のenum値、例: ubuntu keyへ`update`）が拒否されること。
   - 未知の文字列値が拒否されること、かつ拒否値そのものがエラーメッセージへ露出しないこと。
   - 非文字列値(int/bool)が拒否されること。
   - operation keyをnative `params`側へ置いた場合に未知keyとして拒否されること。
5. 既存契約の非回帰: 未知top-levelキー拒否、`params`内未知キー拒否、既存primitive
   (`force_renew`/`dry_run`/`debug_level`)が引き続き許可されることを確認する。

## 3. 実行順序

1. 既存test/checkの再実行(§2.1)。
2. job #1027相当schedule fixtureでのpreflight→diff追試(§2.2)。
3. 独立spot-check(§2.3〜2.5)をPythonで直接実行。
4. 結果をtest_resultへ記録。
