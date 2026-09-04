"""Import-time side effect: put roles/syslog_weekly_digest/filter_plugins/
on sys.path so `import syslog_weekly_digest` resolves to the repo's actual
filter plugin file (the same file Ansible loads at runtime), not a copy.

Mirrors scripts/tests/semaphore_schedules/_path_setup.py, this repo's
established pattern for filter plugin unit tests.
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))
_FILTER_PLUGINS_DIR = os.path.join(_REPO_ROOT, "roles", "syslog_weekly_digest", "filter_plugins")

if not os.path.isdir(_FILTER_PLUGINS_DIR):
    raise RuntimeError("filter_plugins dir not found: {}".format(_FILTER_PLUGINS_DIR))

if _FILTER_PLUGINS_DIR not in sys.path:
    sys.path.insert(0, _FILTER_PLUGINS_DIR)
