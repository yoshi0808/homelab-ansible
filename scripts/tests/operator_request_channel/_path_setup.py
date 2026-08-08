"""Import-time side effect: put roles/operator_request_channel/files/ on
sys.path so `from oprc import ...` resolves to the repo's actual library
code (the same files that get deployed via `copy` to ansy/quory), not a
copy. Every test_*.py in this directory does `import _path_setup` before
importing anything from `oprc`.
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))
_OPRC_FILES_DIR = os.path.join(_REPO_ROOT, "roles", "operator_request_channel", "files")

if not os.path.isdir(_OPRC_FILES_DIR):
    raise RuntimeError("oprc files dir not found: {}".format(_OPRC_FILES_DIR))

if _OPRC_FILES_DIR not in sys.path:
    sys.path.insert(0, _OPRC_FILES_DIR)

SCHEMA_PATH = os.path.join(_OPRC_FILES_DIR, "request-schema-v1.json")
DLP_RULES_PATH = os.path.join(_OPRC_FILES_DIR, "dlp-rules.json")
