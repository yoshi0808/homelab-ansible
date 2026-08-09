#!/usr/bin/env python3
"""Offline test runner for roles/semaphore_templates/filter_plugins/
semaphore_schedules.py.

Plain `unittest`, mirroring scripts/tests/operator_request_channel/run-
tests.py (this repo's established precedent for filter/library unit
tests -- no pytest/bats). Discovers every `test_*.py` in this directory
and runs it; add new test modules here and they are picked up
automatically, no registration needed.

Usage:
    python3 scripts/tests/semaphore_schedules/run-tests.py [-v]

Touches no real host and no network: every test operates on plain Python
dict/list fixtures built in-process.
"""

import os
import sys
import unittest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=_THIS_DIR, pattern="test_*.py", top_level_dir=_THIS_DIR)
    verbosity = 2 if "-v" in sys.argv[1:] else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
