import json
import unittest

import _path_setup  # noqa: F401
from semaphore_templates import (
    semaphore_reconcile_marker_actual,
    semaphore_reconcile_marker_freshness,
    semaphore_templates_orphan_baseline_diff,
)
from semaphore_schedules import (
    semaphore_reconcile_update_plan,
    semaphore_schedules_canonical_environment,
    semaphore_schedules_friday_paused,
    semaphore_schedules_diff,
    semaphore_schedules_preflight,
)


class OrphanBaselineTests(unittest.TestCase):
    def test_normalizes_whitespace_and_leading_dot_slash(self):
        result = semaphore_templates_orphan_baseline_diff(
            [{'name': '  SEMI-SAFE:  Semaphore   templates setup ',
              'playbook': './playbooks/semaphore_templates_setup.yml'}],
            [{'name': 'SEMI-SAFE: Semaphore templates setup',
              'playbook': 'playbooks/semaphore_templates_setup.yml'}],
        )
        self.assertEqual(result['errors'], [])
        self.assertFalse(result['changed'])

    def test_detects_same_count_replacement_and_duplicate_growth(self):
        baseline = [{'name': 'a', 'playbook': 'a.yml'}]
        replaced = semaphore_templates_orphan_baseline_diff(
            [{'name': 'b', 'playbook': 'b.yml'}], baseline)
        duplicated = semaphore_templates_orphan_baseline_diff(
            baseline + baseline, baseline)
        self.assertTrue(replaced['changed'])
        self.assertTrue(duplicated['changed'])

    def test_detects_addition_and_removal_but_ignores_order_only(self):
        baseline = [
            {'name': 'a', 'playbook': 'a.yml'},
            {'name': 'b', 'playbook': 'b.yml'},
        ]
        self.assertTrue(semaphore_templates_orphan_baseline_diff(
            baseline + [{'name': 'c', 'playbook': 'c.yml'}], baseline)['changed'])
        self.assertTrue(semaphore_templates_orphan_baseline_diff(
            baseline[:1], baseline)['changed'])
        self.assertFalse(semaphore_templates_orphan_baseline_diff(
            list(reversed(baseline)), baseline)['changed'])

    def test_rejects_missing_or_malformed_baseline(self):
        for baseline in (None, 'bad', [{'name': 'a'}]):
            with self.subTest(baseline=baseline):
                self.assertTrue(semaphore_templates_orphan_baseline_diff([], baseline)['errors'])


class ReconcileFreshnessTests(unittest.TestCase):
    now = '2026-09-16T00:40:00+09:00'

    def evaluate(self, completed_at):
        content = json.dumps({'completed_at': completed_at})
        return semaphore_reconcile_marker_freshness(content, True, True, self.now)

    def test_normal_phase_age_is_fresh(self):
        self.assertFalse(self.evaluate('2026-09-15T04:00:00+09:00')['stale'])

    def test_exactly_24_hours_and_one_missed_run_are_stale(self):
        self.assertTrue(self.evaluate('2026-09-15T00:40:00+09:00')['stale'])
        self.assertTrue(self.evaluate('2026-09-14T04:00:00+09:00')['stale'])

    def test_missing_nonregular_invalid_and_future_markers_are_stale(self):
        self.assertTrue(semaphore_reconcile_marker_freshness('', False, False, self.now)['stale'])
        self.assertTrue(semaphore_reconcile_marker_freshness('', True, False, self.now)['stale'])
        self.assertTrue(self.evaluate('not-json')['stale'])
        self.assertTrue(self.evaluate('2026-09-17T00:40:00+09:00')['stale'])

    def test_finding_actual_reports_elapsed_seconds_or_the_failure_reason(self):
        stale = self.evaluate('2026-09-15T00:40:00+09:00')
        self.assertEqual(semaphore_reconcile_marker_actual(stale), '86400 seconds')
        missing = semaphore_reconcile_marker_freshness('', False, False, self.now)
        self.assertEqual(semaphore_reconcile_marker_actual(missing), 'markerが欠落')
        self.assertEqual(semaphore_reconcile_marker_actual({'error': None, 'age_seconds': None}),
                         '経過時間を判定できません')


class FridayPausedTests(unittest.TestCase):
    def test_japan_friday_lists_only_inactive_rows(self):
        rows = [
            {'name': 'active', 'active': True},
            {'name': 'paused', 'active': False, 'cron_format': '0 4 * * *'},
        ]
        result = semaphore_schedules_friday_paused(rows, '2026-09-18T10:00:00+09:00')
        self.assertEqual(result, [{'name': 'paused', 'cron_format': '0 4 * * *'}])

    def test_non_friday_suppresses_paused_list(self):
        self.assertEqual(
            semaphore_schedules_friday_paused(
                [{'name': 'paused', 'active': False}], '2026-09-17T10:00:00+09:00'),
            [],
        )


class CombinedUpdateCapTests(unittest.TestCase):
    def test_four_total_updates_are_allowed(self):
        self.assertTrue(semaphore_reconcile_update_plan(2, 2, 4)['allowed'])

    def test_five_updates_are_rejected_in_each_single_resource_and_mixed_case(self):
        for template_count, schedule_count in ((5, 0), (0, 5), (2, 3)):
            with self.subTest(template=template_count, schedules=schedule_count):
                self.assertFalse(
                    semaphore_reconcile_update_plan(template_count, schedule_count, 4)['allowed'])

    def test_invalid_counts_are_rejected(self):
        with self.assertRaises(ValueError):
            semaphore_reconcile_update_plan(True, 0, 4)

    def test_explicit_cap_override_allows_a_reviewed_five_item_change(self):
        self.assertTrue(semaphore_reconcile_update_plan(2, 3, 5)['allowed'])

    def test_new_template_reference_is_pending_in_plan_then_resolves_after_apply(self):
        catalog = [{
            'name': 'daily', 'template': 'new template', 'cron': '0 4 * * *',
            'active': True, 'task_params': {'environment': '{}'},
        }]
        observed_schedules = [{
            'id': 4, 'name': 'daily', 'active': True,
            'cron_format': '0 4 * * *', 'template_id': 1,
        }]
        details = {4: {
            'id': 4, 'name': 'daily', 'active': True,
            'cron_format': '0 4 * * *', 'template_id': 1,
            'task_params': {'environment': '{}'},
        }}
        plan_preflight = semaphore_schedules_preflight(
            catalog, observed_schedules, [{'id': -1, 'name': 'new template'}], True)
        self.assertEqual(plan_preflight['errors'], [])
        planned = semaphore_schedules_diff(
            catalog, plan_preflight['observed_by_name'], details,
            plan_preflight['template_ids'], 'https://quory.internal:3000/api')
        self.assertEqual(planned['changed'][0]['after']['template_id'], -1)

        actual_preflight = semaphore_schedules_preflight(
            catalog, observed_schedules, [{'id': 52, 'name': 'new template'}], True)
        applied_plan = semaphore_schedules_diff(
            catalog, actual_preflight['observed_by_name'], details,
            actual_preflight['template_ids'], 'https://quory.internal:3000/api')
        self.assertEqual(applied_plan['changed'][0]['after']['template_id'], 52)

    def test_bootstrap_environment_uses_the_canonical_filter_constant(self):
        self.assertEqual(
            json.loads(semaphore_schedules_canonical_environment()),
            {
                'semaphore_templates_api_base_url': 'https://quory.internal:3000/api',
                'semaphore_templates_api_validate_certs': 'true',
            },
        )

    def test_reconcile_environment_values_are_fixed_and_fail_closed(self):
        allowed = {
            'semaphore_templates_api_base_url': 'https://quory.internal:3000/api',
            'semaphore_templates_api_validate_certs': 'true',
        }
        entry = {
            'name': 'bootstrap', 'template': 'bootstrap', 'cron': '0 4 * * *',
            'active': True, 'task_params': {'environment': json.dumps(allowed)},
        }
        observed_schedule = {'id': 1, 'name': 'bootstrap', 'active': True}
        observed_template = {'id': 2, 'name': 'bootstrap'}
        accepted = semaphore_schedules_preflight(
            [entry], [observed_schedule], [observed_template], True)
        self.assertEqual(accepted['errors'], [])

        for key, bad_value in (
            ('semaphore_templates_api_base_url', 'https://ansy.internal:3000/api'),
            ('semaphore_templates_api_base_url', 'https://attacker.invalid/api'),
            ('semaphore_templates_api_validate_certs', 'false'),
            ('semaphore_templates_api_validate_certs', False),
        ):
            with self.subTest(key=key, value=bad_value):
                bad_entry = dict(entry)
                bad_environment = dict(allowed)
                bad_environment[key] = bad_value
                bad_entry['task_params'] = {'environment': json.dumps(bad_environment)}
                result = semaphore_schedules_preflight(
                    [bad_entry], [observed_schedule], [observed_template], True)
                self.assertTrue(result['errors'])
                self.assertIn(key, result['errors'][0])


class CurrentCatalogPreflightTests(unittest.TestCase):
    def test_every_checked_in_schedule_catalog_entry_passes_preflight(self):
        import pathlib
        import yaml

        from semaphore_schedules import semaphore_schedules_canonical_environment

        repo_root = pathlib.Path(__file__).resolve().parents[3]
        defaults = yaml.safe_load(
            (repo_root / 'roles/semaphore_templates/defaults/main.yml').read_text())
        catalog = defaults['semaphore_schedules_catalog']
        bootstrap_expression = "{{ '' | semaphore_schedules_canonical_environment }}"
        bootstrap_rows = [row for row in catalog if row.get('name') == 'SEMI-SAFE: Semaphore reconcile daily']
        self.assertEqual(len(bootstrap_rows), 1)
        environment = bootstrap_rows[0]['task_params']['environment']
        self.assertEqual(environment, bootstrap_expression)
        bootstrap_rows[0]['task_params']['environment'] = semaphore_schedules_canonical_environment()

        template_names = sorted({row['template'] for row in catalog})
        template_ids = {name: index + 1 for index, name in enumerate(template_names)}
        observed_templates = [
            {'id': template_ids[name], 'name': name}
            for name in template_names
        ]
        observed_schedules = [
            {
                'id': index + 1,
                'name': row['name'],
                'active': row['active'],
                'cron_format': row['cron'],
                'template_id': template_ids[row['template']],
            }
            for index, row in enumerate(catalog)
        ]
        result = semaphore_schedules_preflight(
            catalog, observed_schedules, observed_templates, True)
        self.assertEqual(result['errors'], [], '\n'.join(result['errors']))


class FinalizerReportingContractsTests(unittest.TestCase):
    def test_successful_atomic_publishes_remove_their_temporary_files(self):
        import pathlib
        import yaml

        repo_root = pathlib.Path(__file__).resolve().parents[3]
        tasks = yaml.safe_load(
            (repo_root / 'roles/semaphore_templates/tasks/reconcile_finalize.yml').read_text())
        run_block = next(task for task in tasks if task.get('name', '').startswith('Save the immutable run report'))
        marker_block = next(task for task in tasks if task.get('name', '').startswith('Publish latest-success'))
        for block, publish_name, cleanup_name in (
            (run_block['block'], 'Atomically publish the immutable run report',
             'Remove the published run-report temporary file'),
            (marker_block['block'], 'Atomically publish latest-success marker after its target report exists (P0-8)',
             'Remove the published latest-success temporary file'),
        ):
            names = [task.get('name') for task in block]
            self.assertLess(names.index(publish_name), names.index(cleanup_name))
            cleanup = block[names.index(cleanup_name)]
            self.assertEqual(cleanup['ansible.builtin.file']['state'], 'absent')
            self.assertFalse(cleanup['failed_when'])

    def test_stale_finding_uses_the_elapsed_age_formatter(self):
        import pathlib

        repo_root = pathlib.Path(__file__).resolve().parents[3]
        task_text = (repo_root / 'roles/deployment_drift_check/tasks/semaphore_probe.yml').read_text()
        self.assertIn('| semaphore_reconcile_marker_actual', task_text)


if __name__ == '__main__':
    unittest.main()
