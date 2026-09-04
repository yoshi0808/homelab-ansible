#!/usr/bin/env python3
"""Offline test runner for syslog_weekly_digest (filter_plugins + collector).

Plain `unittest`, mirroring scripts/tests/semaphore_schedules/run-tests.py
(this repo's established precedent for filter/library unit tests -- no
pytest/bats). Discovers every `test_*.py` in this directory and runs it.

Usage:
    python3 scripts/tests/syslog_weekly_digest/run-tests.py [-v]

test_filters.py touches no real host and no network. test_collector.py
binds a throwaway HTTP server to 127.0.0.1:3100 and runs the real
collector script as a subprocess against it (skips itself if port 3100 is
already in use on the machine running the test). Neither touches any real
Ansible inventory host.
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
