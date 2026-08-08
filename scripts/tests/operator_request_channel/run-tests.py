#!/usr/bin/env python3
"""Offline test runner for the Operator Request Channel library layer
(roles/operator_request_channel/files/oprc/).

Plain `unittest` (this repo has no pytest/bats precedent -- see the
implement record for this case). Discovers every `test_*.py` in this
directory and runs it; add new test modules here and they are picked up
automatically, no registration needed.

Usage:
    python3 scripts/tests/operator_request_channel/run-tests.py [-v]

Touches no real host: every test operates on a `tempfile.TemporaryDirectory`
spool and the repo's own copies of request-schema-v1.json / dlp-rules.json.
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
