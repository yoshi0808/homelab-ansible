import unittest

import _path_setup  # noqa: F401
import _fixtures as fx

from semaphore_schedules import semaphore_schedules_desired, semaphore_schedules_diff


class DesiredStateTests(unittest.TestCase):
    """2026-08-24 (semaphore_activation_gate_removal案件 R1): `stage` と
    `observed_detail` 引数は撤去された。`desired['active']` はカタログの
    `active` を常にそのまま反映する -- 新規・既存を問わない。
    """

    def test_new_entry_active_reflects_the_catalog_true(self):
        entry = fx.catalog_entry('SAFE: Brand new', 'SAFE: Brand new', '30 6 * * *', True)
        desired = semaphore_schedules_desired(entry, 12)
        self.assertEqual(desired['active'], True)
        self.assertIs(desired['active'], True)

    def test_new_entry_active_reflects_the_catalog_false(self):
        entry = fx.catalog_entry('SAFE: Brand new', 'SAFE: Brand new', '30 6 * * *', False)
        desired = semaphore_schedules_desired(entry, 12)
        self.assertEqual(desired['active'], False)

    def test_existing_entry_active_reflects_the_catalog_regardless_of_observed(self):
        """撤去前は observed が false のとき active:true のカタログでも
        desired は false のままだった(有効化は別段階の仕事)。撤去後は
        observed を一切参照しないため、カタログの true がそのまま通る。
        """
        entry = fx.catalog_entry('SAFE: X', 'SAFE: X', '30 6 * * *', True)
        desired = semaphore_schedules_desired(entry, 12)
        self.assertEqual(desired['active'], True)

    def test_existing_entry_deactivation_reflects_the_catalog(self):
        entry = fx.catalog_entry('SAFE: X', 'SAFE: X', '30 6 * * *', False)
        desired = semaphore_schedules_desired(entry, 12)
        self.assertEqual(desired['active'], False)

    def test_desired_fields_come_from_catalog_and_resolved_template_id(self):
        entry = fx.catalog_entry(
            'SAFE: X', 'SAFE: X template', '30 6 * * *', False,
            task_params={'environment': '{"dry_run": true}'},
        )
        desired = semaphore_schedules_desired(entry, 77)
        self.assertEqual(desired['name'], 'SAFE: X')
        self.assertEqual(desired['cron_format'], '30 6 * * *')
        self.assertEqual(desired['template_id'], 77)
        self.assertEqual(desired['task_params'], {'environment': '{"dry_run": true}'})

    def test_task_params_environment_stays_a_json_string_not_reparsed(self):
        """task_params は不透明な塊として扱い、environment の JSON 文字列は
        desired へそのまま(str のまま)渡る -- preflight (R9-7) が中身を
        覗くのは検査のためだけで、値そのものを作り替えない。
        """
        entry = fx.catalog_entry(
            'SAFE: X', 'SAFE: X', '30 6 * * *', False,
            task_params={'environment': '{"dry_run": true}'},
        )
        desired = semaphore_schedules_desired(entry, 77)
        self.assertIsInstance(desired['task_params']['environment'], str)
        self.assertEqual(desired['task_params']['environment'], '{"dry_run": true}')
        self.assertIs(desired['task_params'], entry['task_params'])


class DiffTests(unittest.TestCase):
    def _run(self, catalog):
        return semaphore_schedules_diff(
            catalog, fx.baseline_observed_by_name(),
            fx.baseline_detail_by_id(), fx.baseline_template_ids(),
        )

    def test_baseline_is_fully_unchanged(self):
        result = self._run(fx.baseline_catalog())
        self.assertEqual(result['new'], [])
        self.assertEqual(result['changed'], [])
        self.assertEqual(
            sorted(result['unchanged']),
            sorted(['SAFE: Time sync check', 'SAFE: Authy healthcheck daily']),
        )

    def test_new_entry_is_reported_with_desired_active_matching_the_catalog(self):
        """2026-08-24(semaphore_activation_gate_removal案件 R1): 撤去前は
        新規は常に active:false で作られた(別段階での有効化待ち)。撤去後は
        カタログの active がそのまま反映される -- ここでは true。
        """
        catalog = fx.baseline_catalog()
        catalog.append(fx.catalog_entry('SAFE: New thing', 'SAFE: New thing', '30 6 * * *', True))
        template_ids = fx.baseline_template_ids()
        template_ids['SAFE: New thing'] = 55
        result = semaphore_schedules_diff(
            catalog, fx.baseline_observed_by_name(), fx.baseline_detail_by_id(), template_ids,
        )
        self.assertEqual(len(result['new']), 1)
        self.assertEqual(result['new'][0]['name'], 'SAFE: New thing')
        self.assertEqual(result['new'][0]['desired']['active'], True)
        self.assertEqual(result['new'][0]['desired']['template_id'], 55)

    def test_cron_change_is_reported_in_changed_with_before_after_and_fields(self):
        catalog = fx.baseline_catalog()
        catalog[1]['cron'] = '0 7 * * *'  # was '30 6 * * *'
        result = self._run(catalog)
        self.assertEqual(len(result['changed']), 1)
        item = result['changed'][0]
        self.assertEqual(item['name'], 'SAFE: Authy healthcheck daily')
        self.assertEqual(item['id'], 22)
        self.assertEqual(item['fields'], ['cron_format'])
        self.assertEqual(item['before']['cron_format'], '30 6 * * *')
        self.assertEqual(item['after']['cron_format'], '0 7 * * *')
        # Only 1 of the 2 catalog entries changed.
        self.assertEqual(result['unchanged'], ['SAFE: Time sync check'])

    def test_deactivation_is_reported_in_changed(self):
        catalog = fx.baseline_catalog()
        catalog[0]['active'] = False  # was True; observed detail 21 is active=True
        result = self._run(catalog)
        self.assertEqual(len(result['changed']), 1)
        item = result['changed'][0]
        self.assertEqual(item['name'], 'SAFE: Time sync check')
        self.assertIn('active', item['fields'])
        self.assertEqual(item['before']['active'], True)
        self.assertEqual(item['after']['active'], False)

    def test_activation_alone_is_reported_in_changed(self):
        """2026-08-24(semaphore_activation_gate_removal案件 R1): 撤去前は
        カタログが active:true・観測が active:false のとき、stage1の
        desiredはobservedのまま(false)になるため'unchanged'へ入り、別途
        'pending_activation'で報告された。撤去後はカタログの active が
        そのままdesiredになるため、他の4項目が一致していても単独で
        'changed'に入る。
        """
        catalog = fx.baseline_catalog()
        catalog[1]['active'] = True  # was False
        catalog[1]['task_params'] = {'environment': '{"debug_level": 4}'}  # matches detail
        detail_by_id = fx.baseline_detail_by_id()
        detail_by_id[22]['active'] = False  # already false; matches observed row too
        observed_rows = fx.baseline_observed_schedules()
        observed_rows[1]['active'] = False
        result = semaphore_schedules_diff(
            catalog, fx.baseline_observed_by_name(observed_rows), detail_by_id,
            fx.baseline_template_ids(),
        )
        self.assertNotIn('SAFE: Authy healthcheck daily', result['unchanged'])
        self.assertEqual(len(result['changed']), 1)
        item = result['changed'][0]
        self.assertEqual(item['name'], 'SAFE: Authy healthcheck daily')
        self.assertEqual(item['fields'], ['active'])
        self.assertEqual(item['after']['active'], True)

    def test_task_params_round_trips_through_diff_as_the_original_json_string(self):
        catalog = fx.baseline_catalog()
        catalog[1]['cron'] = '0 7 * * *'  # force a changed entry so 'after' is populated
        result = self._run(catalog)
        after_task_params = result['changed'][0]['after']['task_params']
        self.assertIsInstance(after_task_params, dict)
        self.assertIsInstance(after_task_params['environment'], str)
        self.assertEqual(after_task_params['environment'], '{"debug_level": 4}')


if __name__ == "__main__":
    unittest.main()
