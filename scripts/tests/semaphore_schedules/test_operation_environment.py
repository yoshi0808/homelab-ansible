import json
import unittest

import _path_setup  # noqa: F401
import _fixtures as fx

from semaphore_schedules import semaphore_schedules_diff, semaphore_schedules_preflight


class OperationEnvironmentTests(unittest.TestCase):
    def _preflight_single_environment(self, environment):
        catalog = fx.baseline_catalog()
        catalog[0]['task_params'] = {'environment': json.dumps(environment)}
        return semaphore_schedules_preflight(
            catalog,
            fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(),
            closed_world=False,
        )

    def test_each_namespaced_operation_accepts_only_its_enum(self):
        allowed = {
            'ubuntu_vm_full_upgrade_operation': ('inspect', 'apply'),
            'prometheus_update_check_operation': ('inspect', 'update', 'rollback'),
        }
        for key, values in allowed.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    result = self._preflight_single_environment({key: value})
                    self.assertEqual(result['errors'], [])

    def test_unknown_operation_values_are_rejected_without_echoing_value(self):
        for key in (
            'ubuntu_vm_full_upgrade_operation',
            'prometheus_update_check_operation',
        ):
            with self.subTest(key=key):
                result = self._preflight_single_environment({key: 'destroy-everything'})
                self.assertEqual(len(result['errors']), 1, result['errors'])
                self.assertIn(key, result['errors'][0])
                self.assertIn('許可契約', result['errors'][0])
                self.assertNotIn('destroy-everything', result['errors'][0])

    def test_operation_key_is_rejected_in_native_params_axis(self):
        catalog = fx.baseline_catalog()
        catalog[0]['task_params'] = {
            'environment': '{}',
            'params': {'ubuntu_vm_full_upgrade_operation': 1},
        }
        result = semaphore_schedules_preflight(
            catalog,
            fx.baseline_observed_schedules(),
            fx.baseline_observed_templates(),
            closed_world=False,
        )
        self.assertEqual(len(result['errors']), 1, result['errors'])
        self.assertIn('params.ubuntu_vm_full_upgrade_operation', result['errors'][0])
        self.assertIn('許可されていないキー', result['errors'][0])

    def test_job_1027_operation_schedules_pass_preflight_and_diff_in_place(self):
        catalog = [
            fx.catalog_entry(
                'SEMI-SAFE:Ubuntu vm full upgrade(dry_run=true)',
                'SEMI-SAFE: Ubuntu vm full upgrade (dry-run)',
                '15 18 2 * *',
                True,
                task_params={
                    'environment': '{"ubuntu_vm_full_upgrade_operation":"inspect"}',
                    'params': {'dry_run': False},
                },
            ),
            fx.catalog_entry(
                'SAFE:Prometheus update check',
                'SAFE: Prometheus update check (check)',
                '5 17 * * 5',
                True,
                task_params={
                    'environment': '{"prometheus_update_check_operation":"inspect"}',
                    'params': {'debug_level': 4, 'dry_run': False},
                },
            ),
        ]
        templates = [
            {'id': 30, 'name': catalog[0]['template']},
            {'id': 31, 'name': catalog[1]['template']},
        ]
        observed = [
            {'id': 40, 'name': catalog[0]['name']},
            {'id': 41, 'name': catalog[1]['name']},
        ]
        preflight = semaphore_schedules_preflight(
            catalog, observed, templates, closed_world=True,
        )
        self.assertEqual(preflight['errors'], [])
        self.assertEqual(preflight['unmanaged'], [])

        details = {
            40: {
                'id': 40, 'name': catalog[0]['name'], 'cron_format': catalog[0]['cron'],
                'template_id': 30, 'active': True,
                'task_params': {'environment': '{"dry_run":"true"}'},
            },
            41: {
                'id': 41, 'name': catalog[1]['name'], 'cron_format': catalog[1]['cron'],
                'template_id': 31, 'active': True,
                'task_params': {
                    'environment': '{"dry_run":"true"}',
                    'params': {'debug_level': 4, 'dry_run': False},
                },
            },
        }
        diff = semaphore_schedules_diff(
            catalog, preflight['observed_by_name'], details, preflight['template_ids'],
        )
        self.assertEqual(diff['new'], [])
        self.assertEqual(diff['unchanged'], [])
        self.assertEqual([item['id'] for item in diff['changed']], [40, 41])
        self.assertEqual(
            [item['fields'] for item in diff['changed']],
            [['task_params'], ['task_params']],
        )
        self.assertEqual(
            [item['after']['task_params'] for item in diff['changed']],
            [entry['task_params'] for entry in catalog],
        )


if __name__ == '__main__':
    unittest.main()
