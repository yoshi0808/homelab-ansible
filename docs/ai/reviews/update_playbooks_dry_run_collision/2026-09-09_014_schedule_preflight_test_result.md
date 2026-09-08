# test_result: schedule operation key preflight修正

Tester / 2026-09-09
契約: `2026-09-09_013_schedule_preflight_test_plan.md`

## 安全境界の遵守

- 実host、quory、Semaphore API、production Slackへは触れていない。
- catalog reconcile、commit/pushは行っていない。
- 検証はすべて`roles/semaphore_templates/filter_plugins/semaphore_schedules.py`の公開関数を
  Pythonから直接importし、fixtureデータのみで実行した。ネットワーク・ファイルシステムへの
  副作用はない。

## 1. 既存回帰

| コマンド | rc | 結果 |
|---|---:|---|
| `python3 scripts/tests/semaphore_schedules/run-tests.py` | 0 | 97 tests OK |
| `python3 roles/semaphore_templates/tests/task_flow/run_task_flow_tests.py` | 0 | 既存6 scenarios OK |
| `python3 -m py_compile roles/semaphore_templates/filter_plugins/semaphore_schedules.py scripts/tests/semaphore_schedules/test_operation_environment.py` | 0 | 構文OK |
| `python3 scripts/check-doc-consistency.py` | 0 | 3 checks OK |
| `git diff --check` | 0 | whitespaceエラーなし |

Implementer記録(010)・Reviewer記録(011/012)の主張どおりの結果を独立に再実行して確認した。

## 2. job #1027相当schedule 2件のpreflight→diff追試

既存test(`test_job_1027_operation_schedules_pass_preflight_and_diff_in_place`)を実行するだけでなく、
同じfixture構成をこのTester自身が再構築してインタラクティブに実行した(既存testの内部実装を
コピーせず、公開関数`semaphore_schedules_preflight`/`semaphore_schedules_diff`をそのまま呼び出した)。

- `preflight['errors'] == []`, `preflight['unmanaged'] == []`(`closed_world=True`)。
- `diff['new'] == []`, `diff['unchanged'] == []`。
- `diff['changed']`はid `[40, 41]`（既存observed ID）、各`fields == ['task_params']`のみ。

**PASS**。既存schedule 2件はin-place `changed`として検出され、`new`は0件だった(job #1027の
再発防止条件を満たす)。

## 3. 全正規enum値の許可

`test_each_namespaced_operation_accepts_only_its_enum`を実行し、
`ubuntu_vm_full_upgrade_operation`の`inspect`/`apply`、
`prometheus_update_check_operation`の`inspect`/`update`/`rollback`のすべてで
`errors == []`となることを確認した(rc=0、既存test経由)。

## 4. 独立spot-check(Reviewerの確認と同種を自分で再現)

fixtureモジュール(`_fixtures.py`)経由でbaseline catalogを複製し、`task_params.environment`を
差し替えて`semaphore_schedules_preflight(..., closed_world=False)`を直接呼び出した。

| ケース | 結果 | 判定 |
|---|---|---|
| cross-enum: `ubuntu_vm_full_upgrade_operation: "update"`(Prometheusのenum値) | `errors`に1件、`...ubuntu_vm_full_upgrade_operation の値 (str) が許可契約に一致しない` | **PASS**(拒否) |
| 非文字列: `ubuntu_vm_full_upgrade_operation: 1`(int) | 同上、`(int)`として拒否 | **PASS** |
| 非文字列: `prometheus_update_check_operation: True`(bool) | 同上、`(bool)`として拒否(Python上`bool`は`int`のサブクラスだが、実装が`isinstance(value, str)`で判定するため素通りしない) | **PASS** |
| 未知文字列値の非露出: `ubuntu_vm_full_upgrade_operation: "sekrit-token-abc123"` | エラーメッセージに`sekrit-token-abc123`という文字列は一切出現しない(`str not in`で確認) | **PASS**(値非露出) |
| operation keyのnative params混入: `params: {"ubuntu_vm_full_upgrade_operation": 1}` | `task_params.params.ubuntu_vm_full_upgrade_operation は許可されていないキー(現状 force_renew / dry_run / debug_level のみ許可)` | **PASS**(軸混入拒否) |
| 既存契約の非回帰: 未知top-levelキー(`bogus_top`) | `task_params.bogus_top は許可されていないキー(現状 environment / params のみ許可)` | **PASS** |
| 既存契約の非回帰: `params`内未知キー(`unexpected`) | `task_params.params.unexpected は許可されていないキー(現状 force_renew / dry_run / debug_level のみ許可)` | **PASS** |
| 既存契約の非回帰: `force_renew`(string bool)/`dry_run`(bool)/`debug_level`(int)の同時使用 | `errors == []` | **PASS**(既存primitive継続許可) |

## Verdict

**PASS** — 97 unit tests、既存task-flow 6 scenarios、構文、doc consistency、diff checkはすべてrc=0。
job #1027相当のUbuntu/Prometheus 2 scheduleはpublic preflight→public diffを独立再実行でも通り、
既存ID 2件が`changed`(`task_params`のみ)・`new=0`となることを確認した。全正規enum値の許可、
cross-enum・非文字列・未知値の拒否、operation keyのnative params軸への混入拒否、拒否値の
非露出、既存primitive/未知キー契約の非回帰を、Reviewerの確認とは独立に自分で再現して確認した。
blocking findingは無い。

## 未実施項目とその理由

- 実Semaphoreでのcatalog reconcile再実行、schedule readback、通常inspection/Slack通知の観測は、
  実host・quory・API・Slackへ触れない安全境界により本検証の対象外(Incident・010・011・012も
  同じ理由でNot Runとしている)。commit/push後の配備観測としてCoordinator/Yoshinobu側の残作業。

## 残存リスク

- 本修正はfilter plugin(preflight/diffのロジック)に閉じた検証であり、実SemaphoreのAPIレスポンス
  形状がfixtureと完全に一致するかは配備後のreadbackでしか確定しない(update_playbooks_dry_run_collision
  案件のtest_result 009に記録済みの残存リスクと同種)。

対象実装は無変更。次の指示を待ちます。
