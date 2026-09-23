#!/usr/bin/env python3
"""Offline unittest runner for incident-capture exit semantics."""

import os
import sys
import unittest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    suite = unittest.TestLoader().discover(
        start_dir=_THIS_DIR, pattern="test_*.py", top_level_dir=_THIS_DIR
    )
    result = unittest.TextTestRunner(verbosity=2 if "-v" in sys.argv[1:] else 1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
