"""Load the repository's incident-capture collector without copying it."""

import importlib.util
import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))
COLLECTOR_PATH = os.path.join(
    _REPO_ROOT, "roles", "incident_capture", "files", "incident-capture-collector.py"
)

_SPEC = importlib.util.spec_from_file_location("incident_capture_collector", COLLECTOR_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("collector module could not be loaded: {}".format(COLLECTOR_PATH))

collector = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(collector)
