"""Import-time side effect: put roles/semaphore_templates/filter_plugins/ on
sys.path so `import semaphore_schedules` resolves to the repo's actual
filter plugin file (the same file Ansible loads at runtime), not a copy.

Every test_*.py in this directory does `import _path_setup` before
importing `semaphore_schedules`. Mirrors scripts/tests/operator_request_
channel/_path_setup.py, which established this pattern for this repo.
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))
_FILTER_PLUGINS_DIR = os.path.join(_REPO_ROOT, "roles", "semaphore_templates", "filter_plugins")

if not os.path.isdir(_FILTER_PLUGINS_DIR):
    raise RuntimeError("semaphore_templates filter_plugins dir not found: {}".format(_FILTER_PLUGINS_DIR))

if _FILTER_PLUGINS_DIR not in sys.path:
    sys.path.insert(0, _FILTER_PLUGINS_DIR)
