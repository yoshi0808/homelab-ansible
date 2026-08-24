import unittest

import _path_setup  # noqa: F401

from semaphore_schedules import (
    semaphore_schedules_create_payload,
    semaphore_schedules_payload,
    semaphore_schedules_verify,
)


def _single_get_raw():
    """A single GET /schedules/<id> row (requirement §6.5 shape): every
    field a real response carries, including several this module never
    manages (id, project_id, repository_id, delete_after_run, type).
    """
    return {
        'id': 21, 'name': 'SAFE: Time sync check', 'project_id': 3,
        'repository_id': None, 'delete_after_run': False, 'type': '',
        'cron_format': '50 5 * * *', 'template_id': 10, 'active': True,
        'task_params': {'environment': '{}'},
    }


class PayloadTests(unittest.TestCase):
    def test_payload_contains_every_field_of_the_raw_get(self):
        raw = _single_get_raw()
        desired = {
            'name': 'SAFE: Time sync check', 'cron_format': '0 6 * * *',
            'template_id': 10, 'task_params': {'environment': '{"dry_run": true}'},
            'active': True,
        }
        payload = semaphore_schedules_payload(raw, desired)
        self.assertEqual(set(payload.keys()), set(raw.keys()))

    def test_payload_overwrites_only_the_5_managed_fields(self):
        raw = _single_get_raw()
        desired = {
            'name': 'SAFE: Time sync check (renamed)', 'cron_format': '0 6 * * *',
            'template_id': 99, 'task_params': {'environment': '{"dry_run": true}'},
            'active': False,
        }
        payload = semaphore_schedules_payload(raw, desired)
        for field in ('name', 'cron_format', 'template_id', 'task_params', 'active'):
            self.assertEqual(payload[field], desired[field])
        # non-managed fields stay exactly as observed
        self.assertEqual(payload['id'], 21)
        self.assertEqual(payload['project_id'], 3)
        self.assertEqual(payload['repository_id'], None)
        self.assertEqual(payload['delete_after_run'], False)
        self.assertEqual(payload['type'], '')

    def test_payload_does_not_mutate_the_raw_input(self):
        raw = _single_get_raw()
        raw_copy = dict(raw)
        desired = {
            'name': 'changed', 'cron_format': '0 6 * * *', 'template_id': 99,
            'task_params': {'environment': '{}'}, 'active': False,
        }
        semaphore_schedules_payload(raw, desired)
        self.assertEqual(raw, raw_copy)

    def test_task_params_environment_stays_a_json_string_through_payload(self):
        raw = _single_get_raw()
        desired = {
            'name': 'SAFE: Time sync check', 'cron_format': '50 5 * * *',
            'template_id': 10, 'task_params': {'environment': '{"dry_run": true}'},
            'active': True,
        }
        payload = semaphore_schedules_payload(raw, desired)
        self.assertIsInstance(payload['task_params']['environment'], str)
        self.assertEqual(payload['task_params']['environment'], '{"dry_run": true}')


class CreatePayloadTests(unittest.TestCase):
    def test_create_payload_carries_desired_fields_and_project_id(self):
        desired = {
            'name': 'SAFE: Brand new', 'cron_format': '30 6 * * *', 'template_id': 55,
            'task_params': {'environment': '{}'}, 'active': False,
        }
        payload = semaphore_schedules_create_payload(desired, project_id=3)
        self.assertEqual(payload['name'], 'SAFE: Brand new')
        self.assertEqual(payload['project_id'], 3)
        self.assertEqual(payload['template_id'], 55)
        self.assertEqual(payload['cron_format'], '30 6 * * *')
        self.assertEqual(payload['task_params'], {'environment': '{}'})
        self.assertEqual(payload['active'], False)


class VerifyTests(unittest.TestCase):
    def test_exact_match_returns_empty_list(self):
        desired = {
            'name': 'SAFE: X', 'cron_format': '30 6 * * *', 'template_id': 10,
            'task_params': {'environment': '{"dry_run": true}'}, 'active': True,
        }
        raw_after = dict(desired)
        raw_after['id'] = 21  # extra fields on the raw side are fine
        self.assertEqual(semaphore_schedules_verify(raw_after, desired), [])

    def test_dropped_task_params_key_is_detected_as_a_mismatch(self):
        """AC21: API が受理しないキーは HTTP 成功でも黙って捨てられる ->
        単一 GET の再取得で desired と比較したとき task_params が不一致に
        ならなければならない。
        """
        desired = {
            'name': 'SAFE: X', 'cron_format': '30 6 * * *', 'template_id': 10,
            'task_params': {'environment': '{"probe": "keepme"}'}, 'active': True,
        }
        raw_after = dict(desired)
        raw_after['task_params'] = {'environment': '{}'}  # API silently dropped the key
        self.assertEqual(semaphore_schedules_verify(raw_after, desired), ['task_params'])

    def test_bool_vs_numerically_equal_int_active_is_detected_as_a_mismatch(self):
        """Python の `1 == True` に頼って一致と誤判定しないことの確認
        (R16-2「正規化された値…を一致として扱わない」)。
        """
        desired = {
            'name': 'SAFE: X', 'cron_format': '30 6 * * *', 'template_id': 10,
            'task_params': {'environment': '{}'}, 'active': True,
        }
        raw_after = dict(desired)
        raw_after['active'] = 1  # not a bool
        self.assertEqual(semaphore_schedules_verify(raw_after, desired), ['active'])

    def test_multiple_mismatches_are_all_reported(self):
        desired = {
            'name': 'SAFE: X', 'cron_format': '30 6 * * *', 'template_id': 10,
            'task_params': {'environment': '{}'}, 'active': True,
        }
        raw_after = dict(desired)
        raw_after['cron_format'] = '0 0 * * *'
        raw_after['active'] = False
        self.assertEqual(
            sorted(semaphore_schedules_verify(raw_after, desired)),
            sorted(['cron_format', 'active']),
        )


if __name__ == "__main__":
    unittest.main()
