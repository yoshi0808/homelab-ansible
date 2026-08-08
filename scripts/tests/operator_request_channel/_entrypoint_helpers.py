"""Shared harness for testing the three entry-point scripts
(bin/operator-channel-client, bin/oprc-receive, bin/operator-channel) as
real Python modules, in-process -- not as subprocesses.

Why in-process: each script hardcodes `CONFIG_PATH =
"/etc/operator-request-channel/config.json"` deliberately (see each
script's own module docstring) -- accepting a path override from an
environment variable would be exactly the kind of extra flexibility
requirement §10.1/§11 designs against (forced commands and the local CLI
both take fixed, non-configurable inputs). Subprocess testing would need
either that env-var override or a real `/etc/operator-request-channel/`
on this machine, neither of which this test suite may create (no real
host is touched, `docs/ai/roles/implementer.md`). Importing the script as
a module and patching its `CONFIG_PATH` attribute with
`unittest.mock.patch.object` exercises the exact same code path a real
invocation would, without either problem.

The three files live under roles/operator_request_channel/files/bin/
without a .py extension (deployed via `copy`, not installed as a Python
package) -- `importlib.util.spec_from_file_location` loads them as
modules regardless of extension.
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import stat
import sys
from unittest import mock

import _path_setup  # noqa: F401 -- must run first: inserts files/ onto sys.path so `from oprc import ...` resolves both here and inside the loaded entry-point module

_BIN_DIR = os.path.join(_path_setup._OPRC_FILES_DIR, "bin")


def load_entrypoint(name):
    """Import roles/operator_request_channel/files/bin/<name> as a fresh
    module object. Called once per TestCase (not once per test method) is
    fine -- each test still gets an isolated spool directory and its own
    CONFIG_PATH patch, so module-level state (there is none besides the
    `oprc` imports) does not leak between tests."""
    path = os.path.join(_BIN_DIR, name)
    module_name = "oprc_entrypoint_under_test_" + name.replace("-", "_")
    # These files have no .py suffix (deployed via `copy`, not installed as
    # a package), so spec_from_file_location cannot infer a loader from the
    # extension and returns None unless one is supplied explicitly.
    loader = importlib.machinery.SourceFileLoader(module_name, path)
    spec = importlib.util.spec_from_file_location(module_name, path, loader=loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Invocation:
    def __init__(self, exit_code, stdout, stderr):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr

    def json(self):
        return json.loads(self.stdout)


def run_main(module, argv, stdin_bytes=b""):
    """Call `module.main(argv)` with stdin/stdout/stderr redirected,
    normalizing the `sys.exit()` every code path ends with into an
    `Invocation`. `argv[0]` is a placeholder program name; `main()` only
    looks at `argv[1:]`, matching real `sys.argv` semantics."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    old_stdin = sys.stdin
    sys.stdin = io.TextIOWrapper(io.BytesIO(stdin_bytes), encoding="utf-8")
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                module.main(argv)
                code = 0
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    finally:
        sys.stdin = old_stdin
    return Invocation(code, stdout.getvalue(), stderr.getvalue())


def make_spool(root):
    """Create the four spool subdirectories a real server_setup.yml run
    would create (store.py deliberately creates none of them itself)."""
    for name in ("inbox", "outbox", "events", "quarantine-metadata"):
        os.makedirs(os.path.join(root, name), exist_ok=True)


def write_config(path, **overrides):
    doc = dict(overrides)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    return path


def patch_time_synced(oprc_config_module, synced=True):
    """Patch `oprc.config.assert_time_synced` directly rather than trying
    to redirect it via `CHRONYC_PATH`.

    Why: `assert_time_synced`'s signature is
    `assert_time_synced(..., chronyc_path=CHRONYC_PATH)` -- `CHRONYC_PATH`
    is read *once*, at function-definition time, into the function's
    default-argument tuple. Every entry-point script calls
    `config.assert_time_synced()` with no arguments, so patching the
    module attribute `oprc.config.CHRONYC_PATH` afterwards has no effect
    on calls already bound to the frozen default -- the entry point ends
    up running the *real* system `chronyc` regardless (this was verified
    the hard way: an earlier version of this test suite patched
    `CHRONYC_PATH` and every test passed anyway, including the "not
    synchronised" case, because the real `chronyc` on the machine running
    these tests happens to report a synced clock). Patching the function
    itself sidesteps the frozen-default problem entirely and does not
    depend on this machine's actual chrony status.
    """
    if synced:
        return mock.patch.object(oprc_config_module, "assert_time_synced", return_value=None)
    return mock.patch.object(
        oprc_config_module, "assert_time_synced", side_effect=oprc_config_module.TimeSyncError("not synchronised (test double)")
    )


def make_chronyc_ok(path):
    """A `chronyc tracking` stand-in that always reports a synchronized,
    in-bounds clock -- used so tests exercising the create-message path
    are not gated by plan §2.11's time-sync check (that gate has its own
    dedicated tests in test_config.py at the library layer and again at
    the entry-point layer below)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "#!/bin/sh\n"
            "cat <<'EOF'\n"
            "Reference ID    : 00000000 ()\n"
            "Stratum         : 3\n"
            "System time     : 0.000100000 seconds slow of NTP time\n"
            "Leap status     : Normal\n"
            "EOF\n"
            "exit 0\n"
        )
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


def make_chronyc_not_synced(path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "#!/bin/sh\n"
            "cat <<'EOF'\n"
            "System time     : 0.000100000 seconds slow of NTP time\n"
            "Leap status     : Not synchronised\n"
            "EOF\n"
            "exit 0\n"
        )
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path
