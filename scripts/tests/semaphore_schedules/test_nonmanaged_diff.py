"""semaphore_schedules_nonmanaged_diff -- added 2026-08-09 per independent
review High #2: semaphore_schedules_verify only ever compares the 5
managed fields (by design), so a write that silently changed or dropped
something else on the object (`repository_id`, `delete_after_run`,
`type`, ...) would pass unnoticed. AC4 and AC17 both require the
non-managed fields to be confirmed unchanged too.
"""

import unittest

import _path_setup  # noqa: F401

from semaphore_schedules import semaphore_schedules_nonmanaged_diff


def _raw(**overrides):
    raw = {
        'id': 21, 'project_id': 3, 'repository_id': None,
        'delete_after_run': False, 'type': '',
        'name': 'SAFE: Time sync check', 'cron_format': '50 5 * * *',
        'template_id': 10, 'task_params': {'environment': '{}'}, 'active': True,
    }
    raw.update(overrides)
    return raw


class NonmanagedDiffTests(unittest.TestCase):
    def test_identical_raw_objects_have_no_nonmanaged_diff(self):
        before = _raw()
        after = _raw()
        self.assertEqual(semaphore_schedules_nonmanaged_diff(before, after), [])

    def test_managed_fields_changing_is_not_reported_here(self):
        """管理5項目の変化は semaphore_schedules_verify の仕事であり、
        nonmanaged_diff は無視する(二重報告にしない)。
        """
        before = _raw()
        after = _raw(name='SAFE: Renamed', cron_format='0 0 * * *', active=False)
        self.assertEqual(semaphore_schedules_nonmanaged_diff(before, after), [])

    def test_a_changed_nonmanaged_field_is_reported(self):
        before = _raw(repository_id=None)
        after = _raw(repository_id=5)
        self.assertEqual(semaphore_schedules_nonmanaged_diff(before, after), ['repository_id'])

    def test_multiple_changed_nonmanaged_fields_are_all_reported(self):
        before = _raw(delete_after_run=False, type='')
        after = _raw(delete_after_run=True, type='adhoc')
        self.assertEqual(
            sorted(semaphore_schedules_nonmanaged_diff(before, after)),
            sorted(['delete_after_run', 'type']),
        )

    def test_a_nonmanaged_field_dropped_entirely_is_reported(self):
        before = _raw()
        after = _raw()
        del after['repository_id']
        self.assertEqual(semaphore_schedules_nonmanaged_diff(before, after), ['repository_id'])

    def test_a_nonmanaged_field_added_entirely_is_reported(self):
        before = _raw()
        del before['type']
        after = _raw()
        self.assertEqual(semaphore_schedules_nonmanaged_diff(before, after), ['type'])

    def test_uses_the_same_strict_equality_as_verify(self):
        """AC21/R16-2 と同じ規律: `1` と `True` は一致とみなさない。"""
        before = _raw(delete_after_run=False)
        after = _raw(delete_after_run=0)
        self.assertEqual(semaphore_schedules_nonmanaged_diff(before, after), ['delete_after_run'])


if __name__ == "__main__":
    unittest.main()
