"""Offline template read-set and comparison regressions (Phase 1)."""
import importlib.util
import os
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
PLUGIN = os.path.join(ROOT, 'roles/semaphore_templates/filter_plugins/semaphore_templates.py')
spec = importlib.util.spec_from_file_location('semaphore_templates', PLUGIN)
templates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(templates)
import sys
sys.path.insert(0, os.path.join(ROOT, 'scripts/tests/semaphore_schedules'))
import semaphore_schedules
import _fixtures as schedule_fixtures


class TemplateSafetyTests(unittest.TestCase):
    def setUp(self):
        self.entry = {'playbook': 'playbooks/check.yml', 'class': 'SAFE', 'arguments': [],
                      'survey_vars': [{'name': 'x', 'title': 'X', 'required': False,
                                       'default_value': ''}]}
        marker = templates.semaphore_templates_build_marker(self.entry['playbook'])
        self.row = {'id': 1, 'name': 'SAFE: Check', 'playbook': self.entry['playbook'],
                    'arguments': '[]', 'survey_vars': '[{"name":"x","title":"X"}]',
                    'description': marker}

    def test_first_then_second_reconcile_is_idempotent(self):
        first = templates.semaphore_templates_reconcile([self.entry], [])
        self.assertEqual(len(first['new']), 1)
        second = templates.semaphore_templates_reconcile([self.entry], [self.row])
        self.assertEqual(second['changed'], [])
        self.assertEqual(second['new'], [])

    def test_falsy_survey_fields_are_equivalent_when_omitted(self):
        diff = templates.semaphore_templates_reconcile([self.entry], [self.row])
        self.assertEqual(diff['unchanged'], [{'key': 'playbooks/check.yml#-', 'id': 1}])

    def test_false_arguments_equivalent_to_empty_list_but_nonempty_is_not(self):
        false_row = dict(self.row, arguments=False)
        self.assertEqual(templates.semaphore_templates_reconcile([self.entry], [false_row])['changed'], [])
        nonempty = dict(self.row, arguments='["--limit","quory"]')
        self.assertEqual(len(templates.semaphore_templates_reconcile([self.entry], [nonempty])['changed']), 1)

    def test_ac1a_markerless_self_reference_shape_is_allowed_and_remains_orphan(self):
        orphan = {'id': 37, 'name': 'SEMI-SAFE: Semaphore templates setup',
                  'playbook': 'playbooks/semaphore_templates_setup.yml',
                  'arguments': '[]', 'survey_vars': '[]', 'description': ''}
        observed = [self.row, orphan]
        self.assertEqual(templates.semaphore_templates_preflight([self.entry], observed, 2), [])
        result = templates.semaphore_templates_reconcile([self.entry], observed)
        self.assertEqual(result['orphans'], [orphan])

    def test_ac1a_marker_lost_from_catalog_name_fails_closed_before_duplicate_create(self):
        lost_marker = dict(self.row, description='')
        errors = templates.semaphore_templates_preflight([self.entry], [lost_marker], 2)
        self.assertEqual(len(errors), 1)
        self.assertIn('markerless name collides with catalog target', errors[0])
        # The raw comparator would otherwise classify it as orphan + new;
        # the preflight error is the gate that prevents that duplicate POST.
        result = templates.semaphore_templates_reconcile([self.entry], [lost_marker])
        self.assertEqual(result['new'][0]['key'], 'playbooks/check.yml#-')
        self.assertEqual(result['orphans'][0]['id'], 1)

    def test_ac5a_arguments_falsy_forms_pass_preflight_and_compare_equal(self):
        for value in (False, None, '[]', []):
            with self.subTest(value=value):
                row = dict(self.row, arguments=value)
                self.assertEqual(templates.semaphore_templates_preflight([self.entry], [row], 2), [])
                result = templates.semaphore_templates_reconcile([self.entry], [row])
                self.assertEqual(result['changed'], [])
                self.assertEqual(result['unchanged'], [{'key': 'playbooks/check.yml#-', 'id': 1}])

    def test_survey_vars_false_and_null_are_equivalent_to_empty_list(self):
        empty_entry = dict(self.entry, survey_vars=[])
        for value in (False, None, '[]', []):
            with self.subTest(value=value):
                row = dict(self.row, survey_vars=value)
                self.assertEqual(templates.semaphore_templates_preflight([empty_entry], [row], 2), [])
                self.assertEqual(templates.semaphore_templates_reconcile([empty_entry], [row])['changed'], [])

    def test_truthy_bool_is_not_accepted_as_a_falsy_alias(self):
        errors = templates.semaphore_templates_preflight(
            [self.entry], [dict(self.row, arguments=True)], 2)
        self.assertEqual(len(errors), 1)
        self.assertIn('arguments の true', errors[0])

    def test_malformed_survey_type_fails_with_name_and_path(self):
        with self.assertRaisesRegex(ValueError, 'SAFE: Check.*survey_vars'):
            templates.semaphore_templates_reconcile([self.entry], [dict(self.row, survey_vars='invalid')])

    def test_empty_partial_invalid_identity_and_duplicate_are_rejected(self):
        self.assertTrue(templates.semaphore_templates_preflight([self.entry], [], 2))
        self.assertTrue(templates.semaphore_templates_preflight([self.entry], [{**self.row, 'id': None}], 2))
        self.assertTrue(templates.semaphore_templates_preflight(
            [self.entry], [{**self.row, 'description': 'semaphore-templates:playbook=broken'}], 2))
        self.assertTrue(templates.semaphore_templates_preflight([self.entry], [self.row, dict(self.row, id=2)], 2))

    def test_create_cap_is_fail_closed_by_preflight(self):
        two = [self.entry, dict(self.entry, variant='second')]
        self.assertTrue(templates.semaphore_templates_preflight(two, [], 1))

    def test_empty_schedule_api_response_and_invalid_rows_are_preflight_errors(self):
        baseline = schedule_fixtures.baseline_catalog()
        self.assertTrue(semaphore_schedules.semaphore_schedules_readset_preflight(
            baseline, [], 2))
        self.assertTrue(semaphore_schedules.semaphore_schedules_preflight(
            baseline, [], schedule_fixtures.baseline_observed_templates(), False)['errors'])
        rows = schedule_fixtures.baseline_observed_schedules()
        rows[0] = dict(rows[0], id=None)
        self.assertTrue(semaphore_schedules.semaphore_schedules_readset_preflight(
            baseline, rows, 2))
        self.assertTrue(semaphore_schedules.semaphore_schedules_preflight(
            baseline, rows, schedule_fixtures.baseline_observed_templates(), False)['errors'])

    def test_non_mapping_schedule_detail_fails_instead_of_becoming_empty_mapping(self):
        catalog = schedule_fixtures.baseline_catalog()
        with self.assertRaisesRegex(ValueError, 'SAFE: Time sync check.*detail'):
            semaphore_schedules.semaphore_schedules_diff(
                catalog, schedule_fixtures.baseline_observed_by_name(),
                {21: False, 22: schedule_fixtures.baseline_detail_by_id()[22]},
                schedule_fixtures.baseline_template_ids())


if __name__ == '__main__':
    unittest.main()
