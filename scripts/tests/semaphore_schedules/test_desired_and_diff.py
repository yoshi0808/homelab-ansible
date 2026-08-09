import unittest

import _path_setup  # noqa: F401
import _fixtures as fx

from semaphore_schedules import semaphore_schedules_desired, semaphore_schedules_diff


class DesiredStateTests(unittest.TestCase):
    def test_new_entry_stage1_is_always_inactive_even_if_catalog_wants_active(self):
        entry = fx.catalog_entry('SAFE: Brand new', 'SAFE: Brand new', '30 6 * * *', True)
        desired = semaphore_schedules_desired(entry, None, 12, stage=1)
        self.assertEqual(desired['active'], False)  # R13
        self.assertIs(desired['active'], False)

    def test_existing_entry_stage1_never_activates_even_if_catalog_wants_active(self):
        entry = fx.catalog_entry('SAFE: X', 'SAFE: X', '30 6 * * *', True)
        observed_detail = {'active': False}
        desired = semaphore_schedules_desired(entry, observed_detail, 12, stage=1)
        self.assertEqual(desired['active'], False)

    def test_existing_entry_stage1_keeps_observed_active_true(self):
        entry = fx.catalog_entry('SAFE: X', 'SAFE: X', '30 6 * * *', True)
        observed_detail = {'active': True}
        desired = semaphore_schedules_desired(entry, observed_detail, 12, stage=1)
        self.assertEqual(desired['active'], True)

    def test_existing_entry_stage1_immediate_deactivation(self):
        entry = fx.catalog_entry('SAFE: X', 'SAFE: X', '30 6 * * *', False)
        observed_detail = {'active': True}
        desired = semaphore_schedules_desired(entry, observed_detail, 12, stage=1)
        self.assertEqual(desired['active'], False)  # R8-2 即時無効化

    def test_stage2_is_always_active_regardless_of_observed(self):
        entry = fx.catalog_entry('SAFE: X', 'SAFE: X', '30 6 * * *', True)
        desired = semaphore_schedules_desired(entry, {'active': False}, 12, stage=2)
        self.assertEqual(desired['active'], True)

    def test_invalid_stage_raises(self):
        entry = fx.catalog_entry('SAFE: X', 'SAFE: X', '30 6 * * *', True)
        with self.assertRaises(ValueError):
            semaphore_schedules_desired(entry, None, 12, stage=3)

    def test_desired_fields_come_from_catalog_and_resolved_template_id(self):
        entry = fx.catalog_entry(
            'SAFE: X', 'SAFE: X template', '30 6 * * *', False,
            task_params={'environment': '{"dry_run": true}'},
        )
        desired = semaphore_schedules_desired(entry, None, 77, stage=1)
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
        desired = semaphore_schedules_desired(entry, None, 77, stage=1)
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
        self.assertEqual(result['stage1'], [])
        self.assertEqual(
            sorted(result['unchanged']),
            sorted(['SAFE: Time sync check', 'SAFE: Authy healthcheck daily']),
        )
        self.assertEqual(result['pending_activation'], [])

    def test_new_entry_is_reported_with_inactive_desired_state(self):
        catalog = fx.baseline_catalog()
        catalog.append(fx.catalog_entry('SAFE: New thing', 'SAFE: New thing', '30 6 * * *', True))
        template_ids = fx.baseline_template_ids()
        template_ids['SAFE: New thing'] = 55
        result = semaphore_schedules_diff(
            catalog, fx.baseline_observed_by_name(), fx.baseline_detail_by_id(), template_ids,
        )
        self.assertEqual(len(result['new']), 1)
        self.assertEqual(result['new'][0]['name'], 'SAFE: New thing')
        self.assertEqual(result['new'][0]['desired']['active'], False)  # R13
        self.assertEqual(result['new'][0]['desired']['template_id'], 55)

    def test_cron_change_is_reported_in_stage1_with_before_after_and_fields(self):
        catalog = fx.baseline_catalog()
        catalog[1]['cron'] = '0 7 * * *'  # was '30 6 * * *'
        result = self._run(catalog)
        self.assertEqual(len(result['stage1']), 1)
        item = result['stage1'][0]
        self.assertEqual(item['name'], 'SAFE: Authy healthcheck daily')
        self.assertEqual(item['id'], 22)
        self.assertEqual(item['fields'], ['cron_format'])
        self.assertEqual(item['before']['cron_format'], '30 6 * * *')
        self.assertEqual(item['after']['cron_format'], '0 7 * * *')
        # Only 1 of the 2 catalog entries changed.
        self.assertEqual(result['unchanged'], ['SAFE: Time sync check'])

    def test_immediate_deactivation_is_reported_in_stage1(self):
        catalog = fx.baseline_catalog()
        catalog[0]['active'] = False  # was True; observed detail 21 is active=True
        result = self._run(catalog)
        self.assertEqual(len(result['stage1']), 1)
        item = result['stage1'][0]
        self.assertEqual(item['name'], 'SAFE: Time sync check')
        self.assertIn('active', item['fields'])
        self.assertEqual(item['before']['active'], True)
        self.assertEqual(item['after']['active'], False)
        # Deactivation is a stage1 write, never a pending activation.
        self.assertEqual(result['pending_activation'], [])

    def test_activation_alone_is_not_a_stage1_change_but_is_pending(self):
        """カタログが active:true、観測が active:false、他の4項目は一致 ->
        stage1 の active は observed のまま(=false)を desired にするため
        'unchanged' に入り、かつ 'pending_activation' にも入る(R8-3)。
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
        self.assertIn('SAFE: Authy healthcheck daily', result['unchanged'])
        self.assertEqual(
            result['pending_activation'], [{'name': 'SAFE: Authy healthcheck daily', 'id': 22}],
        )
        self.assertEqual(result['stage1'], [])

    def test_task_params_round_trips_through_diff_as_the_original_json_string(self):
        catalog = fx.baseline_catalog()
        catalog[1]['cron'] = '0 7 * * *'  # force a stage1 entry so 'after' is populated
        result = self._run(catalog)
        after_task_params = result['stage1'][0]['after']['task_params']
        self.assertIsInstance(after_task_params, dict)
        self.assertIsInstance(after_task_params['environment'], str)
        self.assertEqual(after_task_params['environment'], '{"debug_level": 4}')


if __name__ == "__main__":
    unittest.main()
