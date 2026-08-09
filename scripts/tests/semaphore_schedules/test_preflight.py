import json
import unittest

import _path_setup  # noqa: F401
import _fixtures as fx

from semaphore_schedules import semaphore_schedules_preflight


class PreflightBaselineTests(unittest.TestCase):
    """The shared baseline fixture is constructed so all 7 checks pass in
    both phases (catalog names == observed schedule names exactly), so it
    is used as the "everything else is fine" starting point for every
    isolation test below.
    """

    def test_baseline_migration_phase_has_no_errors(self):
        result = semaphore_schedules_preflight(
            fx.baseline_catalog(), fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['unmanaged'], [])

    def test_baseline_closed_world_phase_has_no_errors(self):
        result = semaphore_schedules_preflight(
            fx.baseline_catalog(), fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=True,
        )
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['unmanaged'], [])

    def test_template_ids_resolved_by_schedule_name(self):
        result = semaphore_schedules_preflight(
            fx.baseline_catalog(), fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(result['template_ids'], fx.baseline_template_ids())

    def test_observed_by_name_is_the_list_get_rows_keyed_by_name(self):
        result = semaphore_schedules_preflight(
            fx.baseline_catalog(), fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        rows = fx.baseline_observed_schedules()
        self.assertEqual(
            result['observed_by_name'],
            {rows[0]['name']: rows[0], rows[1]['name']: rows[1]},
        )


class PreflightIsolationTests(unittest.TestCase):
    """R9's 7 checks must each fire on their own, without the others'
    passing/failing state contaminating them. Each test below breaks
    exactly one check while leaving the rest of the baseline intact, and
    asserts that check's error appears and it is the *only* error.
    """

    # ① カタログ内 schedule 名の重複
    def test_duplicate_catalog_name_is_rejected_alone(self):
        catalog = fx.baseline_catalog()
        catalog.append(dict(catalog[0]))  # exact duplicate of the first entry
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('SAFE: Time sync check', result['errors'][0])
        self.assertIn('重複', result['errors'][0])

    # ② API 側 schedule 名の重複
    def test_duplicate_observed_schedule_name_is_rejected_alone(self):
        observed = fx.baseline_observed_schedules()
        dup_row = dict(observed[0])
        dup_row['id'] = 99  # different id, same name -> duplicate name on API side
        observed.append(dup_row)
        result = semaphore_schedules_preflight(
            fx.baseline_catalog(), observed,
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('SAFE: Time sync check', result['errors'][0])
        self.assertIn('API', result['errors'][0])

    # ③ template 名の解決 -- 0件
    def test_template_resolves_to_zero_matches_is_rejected_alone(self):
        catalog = fx.baseline_catalog()
        catalog[0]['template'] = 'SAFE: Does not exist anywhere'
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('SAFE: Does not exist anywhere', result['errors'][0])
        self.assertIn('0 件', result['errors'][0])
        self.assertNotIn('SAFE: Time sync check', result['template_ids'])

    # ③ template 名の解決 -- 複数件
    def test_template_resolves_to_multiple_matches_is_rejected_alone(self):
        templates = fx.baseline_observed_templates()
        dup_template = dict(templates[0])
        dup_template['id'] = 999  # different id, same name -> ambiguous resolution
        templates.append(dup_template)
        result = semaphore_schedules_preflight(
            fx.baseline_catalog(), fx.baseline_observed_schedules(),
            templates, closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('SAFE: Time sync check', result['errors'][0])
        self.assertIn('2 件', result['errors'][0])

    # ④ cron 文字列の妥当性
    def test_invalid_cron_is_rejected_alone(self):
        catalog = fx.baseline_catalog()
        catalog[0]['cron'] = '99 99 * * *'
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('cron', result['errors'][0])
        self.assertIn('99 99 * * *', result['errors'][0])

    # ⑤ 型と必須項目 -- 必須フィールド欠落
    def test_missing_required_field_is_rejected_alone(self):
        catalog = fx.baseline_catalog()
        del catalog[0]['active']
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn("'active'", result['errors'][0])

    # ⑤ 型と必須項目 -- 型違い
    def test_wrong_type_field_is_rejected_alone(self):
        catalog = fx.baseline_catalog()
        catalog[0]['active'] = 'true'  # str, not bool
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('active', result['errors'][0])
        self.assertIn('bool', result['errors'][0])

    # ⑥ 移行期間: カタログの name が API 側に実在しない
    def test_migration_phase_rejects_name_not_yet_in_api_alone(self):
        catalog = fx.baseline_catalog()
        templates = fx.baseline_observed_templates()
        # New catalog entry whose *template* resolves fine (so ③ passes),
        # but whose *schedule* has no counterpart in observed_schedules yet.
        catalog.append(fx.catalog_entry(
            'SAFE: New thing', 'SAFE: New thing', '30 6 * * *', False,
        ))
        templates.append({
            'id': 12, 'name': 'SAFE: New thing',
            'playbook': 'playbooks/new_thing.yml',
            'arguments': [], 'survey_vars': [], 'description': '',
        })
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(), templates, closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('SAFE: New thing', result['errors'][0])
        self.assertIn('移行期間', result['errors'][0])

    # ⑥ closed-world: 管理外 schedule がある
    def test_closed_world_rejects_unmanaged_schedule_alone(self):
        observed = fx.baseline_observed_schedules()
        observed.append({
            'active': True, 'cron_format': '0 0 * * *', 'delete_after_run': False,
            'id': 30, 'name': 'UN-SAFE: Hand made in UI', 'project_id': 3,
            'repository_id': None, 'template_id': 40,
            'tpl_name': 'UN-SAFE: Hand made in UI', 'type': '',
        })
        result = semaphore_schedules_preflight(
            fx.baseline_catalog(), observed, fx.baseline_observed_templates(), closed_world=True,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('UN-SAFE: Hand made in UI', result['errors'][0])
        self.assertIn('closed-world', result['errors'][0])
        self.assertEqual(result['unmanaged'], [{'id': 30, 'name': 'UN-SAFE: Hand made in UI'}])

    # 同じ管理外行が、移行期間ではエラーにならず一覧にだけ載ることの確認
    def test_migration_phase_reports_unmanaged_without_error(self):
        observed = fx.baseline_observed_schedules()
        observed.append({
            'active': True, 'cron_format': '0 0 * * *', 'delete_after_run': False,
            'id': 30, 'name': 'UN-SAFE: Hand made in UI', 'project_id': 3,
            'repository_id': None, 'template_id': 40,
            'tpl_name': 'UN-SAFE: Hand made in UI', 'type': '',
        })
        result = semaphore_schedules_preflight(
            fx.baseline_catalog(), observed, fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['unmanaged'], [{'id': 30, 'name': 'UN-SAFE: Hand made in UI'}])

    # ⑦ task_params: 秘密情報らしいキー(現在の判定基準ではallowlist外のキーとして拒否される)
    def test_task_params_secret_looking_key_is_rejected_alone(self):
        catalog = fx.baseline_catalog()
        catalog[0]['task_params'] = {
            'environment': json.dumps({'password': 'hunter2'}),
        }
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('SAFE: Time sync check', result['errors'][0])
        self.assertIn('password', result['errors'][0])
        # 候補値そのものはエラー本文に載らない(2026-08-09 review High #3)。
        self.assertNotIn('hunter2', result['errors'][0])

    # ⑦ task_params: allowlist に無い未知の environment 値(秘密らしいpatternに
    # 一致しなくても拒否される -- fail-open だった旧実装への回帰テスト)
    def test_task_params_unrecognized_environment_value_is_rejected_alone(self):
        catalog = fx.baseline_catalog()
        catalog[0]['task_params'] = {
            'environment': json.dumps({'opaque': 'not-classifiable-value'}),
        }
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('opaque', result['errors'][0])
        self.assertIn('許可されていない', result['errors'][0])
        # 候補値そのものはエラー本文に載らない。
        self.assertNotIn('not-classifiable-value', result['errors'][0])

    # ⑦ task_params: 既知キーでも値の型が許可されていない(str/dict/listは拒否)
    def test_task_params_known_key_with_disallowed_value_type_is_rejected_alone(self):
        catalog = fx.baseline_catalog()
        catalog[0]['task_params'] = {
            'environment': json.dumps({'debug_level': 'verbose'}),  # str, not int
        }
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('debug_level', result['errors'][0])
        self.assertNotIn('verbose', result['errors'][0])

    # ⑦ task_params: environment / params 以外のトップレベルキーは allowlist 外
    # (2026-08-09 実測で params も allowlist に加わったため、`environment`/
    # `params` 以外の第3のキーで検査する)
    def test_task_params_unrecognized_top_level_key_is_rejected_alone(self):
        catalog = fx.baseline_catalog()
        catalog[0]['task_params'] = {'metadata': {'author': 'someone'}}
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('metadata', result['errors'][0])
        self.assertIn('許可されていない', result['errors'][0])

    # ⑦ task_params.params が dict でない(2026-08-09 実測により params は
    # allowlist 済みのキーになったので、値の形も別途検査する)
    def test_task_params_params_value_not_a_dict_is_rejected_alone(self):
        catalog = fx.baseline_catalog()
        catalog[0]['task_params'] = {'params': ['--dry-run']}
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('params', result['errors'][0])
        self.assertIn('dict', result['errors'][0])

    # ⑦ task_params.params 内の未知キー
    def test_task_params_params_unrecognized_key_is_rejected_alone(self):
        catalog = fx.baseline_catalog()
        catalog[0]['task_params'] = {'params': {'unexpected_control': 'arbitrary'}}
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('unexpected_control', result['errors'][0])
        self.assertNotIn('arbitrary', result['errors'][0])

    # ⑦ task_params.params 内の既知キーでも値の型が許可されていない
    # (params はネイティブ型のみ許可。environment と違い文字列 "true"/"false" も不可)
    def test_task_params_params_known_key_with_string_value_is_rejected_alone(self):
        catalog = fx.baseline_catalog()
        catalog[0]['task_params'] = {'params': {'dry_run': 'true'}}
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('params.dry_run', result['errors'][0])
        self.assertNotIn("'true'", result['errors'][0])

    # ⑦ task_params: environment 内の "true"/"false" 以外の文字列は
    # stringified primitive として認識されない
    def test_task_params_environment_unrecognized_string_value_is_rejected_alone(self):
        catalog = fx.baseline_catalog()
        catalog[0]['task_params'] = {'environment': json.dumps({'dry_run': 'yes'})}
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('environment.dry_run', result['errors'][0])
        self.assertNotIn('yes', result['errors'][0])

    # ⑦ 2026-08-09 実測: ansy稼働中19件が実際に持つ4種類の task_params の形は、
    # いずれもエラーにならない(独立レビュー後の差し戻し理由そのものの回帰テスト)。
    def test_all_4_real_observed_task_params_shapes_produce_no_error(self):
        for task_params in fx.REAL_TASK_PARAMS_FIXTURES:
            with self.subTest(task_params=task_params):
                catalog = fx.baseline_catalog()
                catalog[0]['task_params'] = task_params
                result = semaphore_schedules_preflight(
                    catalog, fx.baseline_observed_schedules(),
                    fx.baseline_observed_templates(), closed_world=False,
                )
                self.assertEqual(result['errors'], [])

    # ⑦ task_params: environment が JSON として解析できない(判定不能 -> 停止)
    def test_task_params_unparsable_environment_is_rejected_alone(self):
        catalog = fx.baseline_catalog()
        catalog[0]['task_params'] = {'environment': 'not-json{'}
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('JSON', result['errors'][0])
        self.assertNotIn('not-json{', result['errors'][0])

    # ⑦ 実測どおりの安全な値(dry_run/force_renew/debug_level、空environment)はエラーにならない
    def test_task_params_realistic_safe_values_produce_no_error(self):
        catalog = fx.baseline_catalog()
        catalog[0]['task_params'] = {
            'environment': json.dumps({'dry_run': True}),
        }
        catalog[1]['task_params'] = {
            'environment': json.dumps({'force_renew': False, 'debug_level': 4}),
        }
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(result['errors'], [])

    def test_task_params_empty_environment_produces_no_error(self):
        catalog = fx.baseline_catalog()
        catalog[0]['task_params'] = {'environment': '{}'}
        result = semaphore_schedules_preflight(
            catalog, fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(), closed_world=False,
        )
        self.assertEqual(result['errors'], [])


if __name__ == "__main__":
    unittest.main()
