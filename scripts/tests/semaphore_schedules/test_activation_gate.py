import unittest

import _path_setup  # noqa: F401

from semaphore_schedules import semaphore_schedules_activation_gate

_CANONICAL = 'https://ansy.example.internal:3000/api'


def _call(**overrides):
    kwargs = dict(
        api_base_url=_CANONICAL,
        canonical_url=_CANONICAL,
        allow_flag=True,
        closed_world=True,
        unmanaged_count=0,
        preflight_ids={1, 2, 3},
        current_ids={1, 2, 3},
    )
    kwargs.update(overrides)
    return semaphore_schedules_activation_gate(**kwargs)


class ActivationGateHappyPathTests(unittest.TestCase):
    def test_all_5_conditions_satisfied_is_the_only_way_to_get_allowed(self):
        result = _call()
        self.assertTrue(result['allowed'])
        self.assertEqual(result['reasons'], [])

    def test_trailing_slash_notation_difference_still_matches_canonical(self):
        """R15: 正規化は表記差(末尾スラッシュ)の吸収までは行う。"""
        result = _call(api_base_url=_CANONICAL + '/')
        self.assertTrue(result['allowed'])
        self.assertEqual(result['reasons'], [])


class ActivationGateDisallowTests(unittest.TestCase):
    def test_migration_phase_disallows(self):
        result = _call(closed_world=False)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('移行期間' in r for r in result['reasons']))

    def test_unmanaged_present_disallows(self):
        result = _call(unmanaged_count=2)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('管理外' in r for r in result['reasons']))

    def test_no_explicit_allow_flag_disallows(self):
        result = _call(allow_flag=False)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('明示' in r for r in result['reasons']))

    def test_alias_hostname_for_the_same_server_is_not_treated_as_canonical(self):
        """R15: 「ansy でなければ許可」という否定判定にしない -- 別名の
        DNS 名が実際に同じサーバへ到達できても許可しない(allowlist)。
        """
        result = _call(api_base_url='https://ansy-alias.example.internal:3000/api')
        self.assertFalse(result['allowed'])
        self.assertTrue(any('一致しない' in r for r in result['reasons']))

    def test_unknown_url_is_not_treated_as_canonical(self):
        result = _call(api_base_url='https://totally-unknown.example.com:3000/api')
        self.assertFalse(result['allowed'])
        self.assertTrue(any('一致しない' in r for r in result['reasons']))

    def test_notation_difference_beyond_trailing_slash_is_not_absorbed(self):
        """ポート番号の違いのような「別表記」は吸収対象ではない。"""
        result = _call(api_base_url='https://ansy.example.internal:3001/api')
        self.assertFalse(result['allowed'])
        self.assertTrue(any('一致しない' in r for r in result['reasons']))

    def test_schedule_set_changed_since_preflight_disallows(self):
        result = _call(current_ids={1, 2, 3, 4})
        self.assertFalse(result['allowed'])
        self.assertTrue(any('集合が変化' in r for r in result['reasons']))

    def test_all_5_conditions_failing_reports_all_5_reasons(self):
        result = _call(
            closed_world=False, unmanaged_count=1, allow_flag=False,
            api_base_url='https://unknown.example.com', current_ids={9},
        )
        self.assertFalse(result['allowed'])
        self.assertEqual(len(result['reasons']), 5)

    def test_url_used_reports_the_normalized_api_base_url(self):
        result = _call(api_base_url=_CANONICAL + '/')
        self.assertEqual(result['url_used'], _CANONICAL)


class ActivationGateNonBoolTypeTests(unittest.TestCase):
    """2026-08-09 review Critical #1, regression coverage. `ansible-
    playbook -e key=value` values are strings -- bare `if not allow_flag`
    treated the non-empty string `"false"` as true. Coordinator reproduced
    this exact pair against the pre-fix code (`allow_flag="false"
    closed_world="true"` -> `allowed: True`); this class re-runs it (and
    the other type-confusion shapes an `-e` value or a stray int could
    take) against the fixed code and requires `allowed: False` every time,
    with every other condition otherwise satisfied.
    """

    def test_coordinators_exact_repro_string_false_and_string_true(self):
        result = _call(allow_flag="false", closed_world="true")
        self.assertFalse(result['allowed'])

    def test_string_allow_flag_disallows_even_when_truthy_looking(self):
        result = _call(allow_flag="true")
        self.assertFalse(result['allowed'])
        self.assertTrue(any('真偽値でない' in r for r in result['reasons']))

    def test_string_closed_world_disallows_even_when_truthy_looking(self):
        result = _call(closed_world="true")
        self.assertFalse(result['allowed'])
        self.assertTrue(any('真偽値でない' in r for r in result['reasons']))

    def test_numeric_1_for_allow_flag_disallows(self):
        result = _call(allow_flag=1)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('真偽値でない' in r for r in result['reasons']))

    def test_numeric_1_for_closed_world_disallows(self):
        result = _call(closed_world=1)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('真偽値でない' in r for r in result['reasons']))

    def test_none_for_allow_flag_disallows(self):
        result = _call(allow_flag=None)
        self.assertFalse(result['allowed'])

    def test_type_error_reason_is_distinguishable_from_a_legitimate_disallow_reason(self):
        # A type mistake must not read the same as "not yet closed-world"
        # or "not explicitly allowed" -- a caller (or a human reading the
        # report) needs to be able to tell a setup bug apart from a
        # legitimate, expected disallow.
        type_error_result = _call(allow_flag="false")
        legitimate_result = _call(allow_flag=False)
        self.assertNotEqual(type_error_result['reasons'], legitimate_result['reasons'])
        self.assertFalse(type_error_result['allowed'])
        self.assertFalse(legitimate_result['allowed'])


if __name__ == "__main__":
    unittest.main()
