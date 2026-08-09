import unittest

import _path_setup  # noqa: F401
from _fixtures import INVALID_CRON_FIXTURES, VALID_CRON_FIXTURES

from semaphore_schedules import _cron_is_valid


class CronValidityTests(unittest.TestCase):
    """R9(4). Grammar reconfirmation against the live Semaphore API is
    deferred to test_plan (requirement §9 / §"後続工程へ引き継ぐもの"); this
    only checks the conservative 5-field grammar this module implements.
    """

    def test_all_19_real_cron_strings_are_valid(self):
        for cron in VALID_CRON_FIXTURES:
            with self.subTest(cron=cron):
                self.assertTrue(_cron_is_valid(cron), "expected valid: {!r}".format(cron))

    def test_invalid_cron_strings_are_rejected(self):
        for cron in INVALID_CRON_FIXTURES:
            with self.subTest(cron=cron):
                self.assertFalse(_cron_is_valid(cron), "expected invalid: {!r}".format(cron))


if __name__ == "__main__":
    unittest.main()
