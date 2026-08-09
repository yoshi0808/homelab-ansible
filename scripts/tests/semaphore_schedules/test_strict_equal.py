"""Regression coverage for `_strict_equal`'s 2026-08-09 fix.

Background: the first version of `_strict_equal` required `type(a) is
type(b)` for every value, not just numbers. That over-corrected -- against
real ansible-core (2.20.1), Coordinator measured that a catalog value
(sourced from YAML) and the "same" value taken from an API response
(simulated via `from_json`) come back as *different but value-equal*
classes: `_AnsibleTaggedStr` vs plain `str`, `_AnsibleLazyTemplateDict` vs
plain `dict`. Content and meaning were identical (`a == b` was already
`True`); only the wrapper class differed. The old `type(a) is type(b)`
check rejected every one of those pairs, so `diff`'s stage1 classification,
`verify`, and `stage2_precheck` would all report a change/mismatch that
was never real.

This module reproduces that shape *without importing ansible* -- plain
`str`/`dict` subclasses stand in for ansible-core's wrapper types, which is
sufficient: the bug and the fix both operate purely on `isinstance`/`==`,
not on anything ansible-specific.

`test_payload_and_verify.py::VerifyTests::
test_bool_vs_numerically_equal_int_active_is_detected_as_a_mismatch`
already covers the property this fix must *not* lose (`1` and `True` must
still compare unequal) -- this module does not re-derive that from
scratch, only re-confirms it once at the `_strict_equal` level for
completeness (below), and otherwise focuses on what changed.
"""

import unittest

import _path_setup  # noqa: F401

from semaphore_schedules import (
    _strict_equal,
    semaphore_schedules_diff,
    semaphore_schedules_stage2_precheck,
    semaphore_schedules_verify,
)


class _StrSubclass(str):
    """Stand-in for ansible-core's `_AnsibleTaggedStr` (a `str` subclass
    carrying origin/trust metadata) -- Coordinator's probe found this is
    what a YAML-sourced (catalog) string value actually is at runtime.
    """


class _DictSubclass(dict):
    """Stand-in for ansible-core's `_AnsibleLazyTemplateDict`."""


class StrictEqualSubclassTests(unittest.TestCase):
    def test_str_subclass_equals_plain_str_with_same_content(self):
        self.assertTrue(_strict_equal(_StrSubclass('50 5 * * *'), '50 5 * * *'))
        self.assertTrue(_strict_equal('50 5 * * *', _StrSubclass('50 5 * * *')))

    def test_str_subclass_with_different_content_still_mismatches(self):
        self.assertFalse(_strict_equal(_StrSubclass('50 5 * * *'), '0 6 * * *'))

    def test_dict_subclass_equals_plain_dict_with_same_content(self):
        a = _DictSubclass({'environment': _StrSubclass('{}')})
        b = {'environment': '{}'}
        self.assertTrue(_strict_equal(a, b))

    def test_dict_subclass_with_a_changed_nested_value_still_mismatches(self):
        a = _DictSubclass({'environment': _StrSubclass('{"dry_run": true}')})
        b = {'environment': '{}'}
        self.assertFalse(_strict_equal(a, b))

    def test_mixed_wrapped_and_plain_nested_structure_matches(self):
        # Mirrors a realistic desired-vs-raw comparison: some leaves
        # wrapped (as if templated from YAML), some plain (as if decoded
        # from an API response's JSON), same content throughout.
        a = _DictSubclass({
            'name': _StrSubclass('SAFE: Time sync check'),
            'nested': {'k': _StrSubclass('v')},
            'list': [_StrSubclass('x'), 'y'],
        })
        b = {
            'name': 'SAFE: Time sync check',
            'nested': {'k': 'v'},
            'list': ['x', 'y'],
        }
        self.assertTrue(_strict_equal(a, b))

    def test_bool_vs_int_one_is_still_a_mismatch(self):
        """The property this fix must not lose (R16-2)."""
        self.assertFalse(_strict_equal(True, 1))
        self.assertFalse(_strict_equal(1, True))

    def test_int_subclass_still_participates_in_the_numeric_kind_guard(self):
        class _IntSubclass(int):
            pass

        self.assertTrue(_strict_equal(_IntSubclass(5), 5))       # same kind, same value
        self.assertFalse(_strict_equal(_IntSubclass(1), True))   # int-kind vs bool-kind


def _wrapped_desired():
    """A `desired` dict shaped as if every string/dict leaf had gone
    through Jinja templating from YAML (as `semaphore_schedules_desired`
    building it from a real catalog entry actually would, per
    Coordinator's probe)."""
    return {
        'name': _StrSubclass('SAFE: Time sync check'),
        'cron_format': _StrSubclass('50 5 * * *'),
        'template_id': 10,
        'task_params': _DictSubclass({'environment': _StrSubclass('{}')}),
        'active': True,
    }


def _plain_raw(**overrides):
    """A raw schedule object shaped as if decoded via `from_json` from a
    real API response body (plain str/dict throughout)."""
    raw = {
        'id': 21, 'project_id': 3, 'repository_id': None,
        'delete_after_run': False, 'type': '',
        'name': 'SAFE: Time sync check', 'cron_format': '50 5 * * *',
        'template_id': 10, 'task_params': {'environment': '{}'}, 'active': True,
    }
    raw.update(overrides)
    return raw


class VerifyAcceptsEquivalentWrapperTypesTests(unittest.TestCase):
    def test_verify_reports_no_mismatch_for_value_equal_wrapped_vs_plain(self):
        self.assertEqual(semaphore_schedules_verify(_plain_raw(), _wrapped_desired()), [])

    def test_verify_still_reports_a_real_content_mismatch(self):
        mismatched = semaphore_schedules_verify(
            _plain_raw(cron_format='0 0 * * *'), _wrapped_desired(),
        )
        self.assertEqual(mismatched, ['cron_format'])


class Stage2PrecheckAcceptsEquivalentWrapperTypesTests(unittest.TestCase):
    def test_stage2_precheck_reports_no_mismatch_for_value_equal_wrapped_vs_plain(self):
        stage1_desired = _wrapped_desired()
        del stage1_desired['active']  # stage1_verified_desired carries the 4 non-active fields
        raw_detail = _plain_raw(active=False)
        self.assertEqual(semaphore_schedules_stage2_precheck(raw_detail, stage1_desired), [])

    def test_stage2_precheck_still_reports_a_real_content_mismatch(self):
        stage1_desired = _wrapped_desired()
        del stage1_desired['active']
        raw_detail = _plain_raw(active=False, template_id=99)
        self.assertEqual(
            semaphore_schedules_stage2_precheck(raw_detail, stage1_desired), ['template_id'],
        )


class DiffStage1AcceptsEquivalentWrapperTypesTests(unittest.TestCase):
    def test_value_equal_wrapped_catalog_vs_plain_api_detail_is_unchanged_not_stage1(self):
        catalog = [{
            'name': _StrSubclass('SAFE: Time sync check'),
            'template': _StrSubclass('SAFE: Time sync check'),
            'cron': _StrSubclass('50 5 * * *'),
            'active': True,
            'task_params': _DictSubclass({'environment': _StrSubclass('{}')}),
        }]
        observed_row = {
            'id': 21, 'name': 'SAFE: Time sync check', 'active': True,
            'cron_format': '50 5 * * *', 'template_id': 10,
        }
        observed_by_name = {'SAFE: Time sync check': observed_row}
        detail_by_id = {21: _plain_raw()}
        template_ids = {'SAFE: Time sync check': 10}

        result = semaphore_schedules_diff(catalog, observed_by_name, detail_by_id, template_ids)

        self.assertEqual(result['stage1'], [])
        self.assertEqual(result['unchanged'], ['SAFE: Time sync check'])

    def test_a_real_content_difference_still_lands_in_stage1(self):
        catalog = [{
            'name': _StrSubclass('SAFE: Time sync check'),
            'template': _StrSubclass('SAFE: Time sync check'),
            'cron': _StrSubclass('0 7 * * *'),  # differs from detail's '50 5 * * *'
            'active': True,
            'task_params': _DictSubclass({'environment': _StrSubclass('{}')}),
        }]
        observed_row = {
            'id': 21, 'name': 'SAFE: Time sync check', 'active': True,
            'cron_format': '50 5 * * *', 'template_id': 10,
        }
        observed_by_name = {'SAFE: Time sync check': observed_row}
        detail_by_id = {21: _plain_raw()}
        template_ids = {'SAFE: Time sync check': 10}

        result = semaphore_schedules_diff(catalog, observed_by_name, detail_by_id, template_ids)

        self.assertEqual(len(result['stage1']), 1)
        self.assertEqual(result['stage1'][0]['fields'], ['cron_format'])
        self.assertEqual(result['unchanged'], [])


if __name__ == "__main__":
    unittest.main()
