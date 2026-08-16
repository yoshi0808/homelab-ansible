#!/usr/bin/env python3
"""Fixture tests for roles/agmsg_server/files/prune-stale-ufw-rule.py.

Not deployed to any host -- this is a standalone, ufw-free test of the
script's pure classification/precondition logic and its exit-code
contract, run against synthetic `ufw status` text. It exists because the
one thing a live single-happy-path dummy-rule test against the real ufw
(as used during implementation) cannot show is what the script does when
the input does NOT look like the happy path: ufw inactive, default-allow
incoming, an unrecognized rule shape for the target port, or a delete
`ufw` itself refuses partway through. Independent review round 3 flagged
exactly these gaps -- the two Critical findings and the TOCTOU
Suggestion. Source addresses below are deliberately non-IP-shaped
placeholder tokens (docs/ai/core.md -- no IPv4 literals in the repo);
the script under test treats a source as an opaque string, so this does
not weaken what is being exercised.

Run: python3 roles/agmsg_server/tests/test_prune_stale_ufw_rule.py
"""
import importlib.util
import pathlib
import subprocess
import sys

SCRIPT_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "files" / "prune-stale-ufw-rule.py"
)

_spec = importlib.util.spec_from_file_location("prune_stale_ufw_rule", SCRIPT_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

_failures = []


def check(name, condition):
    if condition:
        print("PASS: {}".format(name))
    else:
        print("FAIL: {}".format(name))
        _failures.append(name)


KEEP_ADDR = "KEEP-ADDR"
STALE_ADDR_A = "STALE-ADDR-A"
STALE_ADDR_B = "STALE-ADDR-B"

# --- is_active_default_deny() ---------------------------------------------

ACTIVE_DEFAULT_DENY = (
    "Status: active\n"
    "Logging: on (low)\n"
    "Default: deny (incoming), allow (outgoing), disabled (routed)\n"
)
check(
    "active + default-deny is recognized as safe",
    mod.is_active_default_deny(ACTIVE_DEFAULT_DENY) is True,
)

INACTIVE = "Status: inactive\n"
check("inactive is refused", mod.is_active_default_deny(INACTIVE) is False)

DEFAULT_ALLOW = (
    "Status: active\n"
    "Logging: on (low)\n"
    "Default: allow (incoming), deny (outgoing), disabled (routed)\n"
)
check(
    "active but default-allow incoming is refused",
    mod.is_active_default_deny(DEFAULT_ALLOW) is False,
)

# --- classify() -------------------------------------------------------------

NO_STALE = (
    "Status: active\n\n"
    "     To                         Action      From\n"
    "     --                         ------      ----\n"
    "[ 1] 22/tcp                     ALLOW IN    Anywhere\n"
    "[ 2] 8788/tcp                   ALLOW IN    {}   # agmsg_server\n".format(KEEP_ADDR)
)
stale, unrecognized = mod.classify(NO_STALE, "8788", KEEP_ADDR)
check("no stale rules when the only rule matches keep_ip", stale == [] and unrecognized == [])

MULTI_STALE = (
    "[ 1] 8788/tcp                   ALLOW IN    {}   # agmsg_server\n".format(KEEP_ADDR)
    + "[ 2] 8788/tcp                   ALLOW IN    {}   # agmsg_server old\n".format(STALE_ADDR_A)
    + "[ 3] 8788/tcp                   ALLOW IN    {}   # agmsg_server older\n".format(STALE_ADDR_B)
    + "[ 4] 3000/tcp                   ALLOW IN    Anywhere\n"
)
stale, unrecognized = mod.classify(MULTI_STALE, "8788", KEEP_ADDR)
check(
    "multiple stale rules for the target port are all found, unrelated port ignored",
    sorted(stale) == sorted([STALE_ADDR_A, STALE_ADDR_B]) and unrecognized == [],
)

UNKNOWN_FORMAT_V6 = (
    "[ 1] 8788/tcp                   ALLOW IN    {}   # agmsg_server\n".format(KEEP_ADDR)
    + "[ 2] 8788/tcp (v6)               ALLOW IN    Anywhere (v6)\n"
)
stale, unrecognized = mod.classify(UNKNOWN_FORMAT_V6, "8788", KEEP_ADDR)
check(
    "an unrecognized line for the target port (e.g. an IPv6 rule) is NOT folded into '0 stale'",
    unrecognized != [] and any("(v6)" in line for line in unrecognized),
)

LOCALE_DIFFERENT_ACTION_WORD = (
    "[ 1] 8788/tcp                   AUTORISER    {}   # translated ufw output\n".format(KEEP_ADDR)
)
stale, unrecognized = mod.classify(LOCALE_DIFFERENT_ACTION_WORD, "8788", KEEP_ADDR)
check(
    "a translated/non-English action word for the target port is unrecognized, not skipped",
    unrecognized != [] and stale == [],
)

NO_RULES_FOR_PORT_AT_ALL = "[ 1] 22/tcp                     ALLOW IN    Anywhere\n"
stale, unrecognized = mod.classify(NO_RULES_FOR_PORT_AT_ALL, "8788", KEEP_ADDR)
check(
    "genuinely no rules for this port at all is 0 stale, 0 unrecognized (a real success case)",
    stale == [] and unrecognized == [],
)

# --- perform_prune(): partial delete failure --------------------------------


def _delete_fails_for_one(fail_src):
    def _delete(src, port):
        if src == fail_src:
            raise subprocess.CalledProcessError(
                1, ["ufw"], stderr="Could not delete non-existent rule\n"
            )

    return _delete


deleted, delete_failures = mod.perform_prune(
    [STALE_ADDR_A, STALE_ADDR_B], "8788", delete=_delete_fails_for_one(STALE_ADDR_B)
)
check(
    "a delete failure for one stale entry does not stop the others, and is reported (not silently dropped)",
    deleted == [STALE_ADDR_A]
    and len(delete_failures) == 1
    and delete_failures[0][0] == STALE_ADDR_B,
)

# --- main(): exit-code contract, ufw calls stubbed --------------------------


def _run_main_with_stubs(status_verbose, status_numbered, delete=None, port="8788", keep_ip=KEEP_ADDR):
    orig_verbose = mod.ufw_status_verbose
    orig_numbered = mod.ufw_status_numbered
    orig_delete = mod.delete_by_spec
    mod.ufw_status_verbose = lambda: status_verbose
    mod.ufw_status_numbered = lambda: status_numbered
    if delete is not None:
        mod.delete_by_spec = delete
    try:
        return mod.main([port, keep_ip])
    finally:
        mod.ufw_status_verbose = orig_verbose
        mod.ufw_status_numbered = orig_numbered
        mod.delete_by_spec = orig_delete


check(
    "main() exits 5 (not 0) when ufw is inactive -- round3 Critical #1 scenario",
    _run_main_with_stubs(INACTIVE, NO_STALE) == 5,
)
check(
    "main() exits 5 (not 0) when default policy is allow incoming",
    _run_main_with_stubs(DEFAULT_ALLOW, NO_STALE) == 5,
)
check(
    "main() exits 3 (not 0) when a rule for the port is unrecognized -- round3 Critical #2 scenario",
    _run_main_with_stubs(ACTIVE_DEFAULT_DENY, UNKNOWN_FORMAT_V6) == 3,
)
check(
    "main() exits 0 with active+default-deny and no stale rules",
    _run_main_with_stubs(ACTIVE_DEFAULT_DENY, NO_STALE) == 0,
)


def _delete_ok(src, port):
    return None


check(
    "main() exits 0 and prunes when active+default-deny and multiple stale rules exist",
    _run_main_with_stubs(ACTIVE_DEFAULT_DENY, MULTI_STALE, delete=_delete_ok) == 0,
)


def _delete_fails(src, port):
    raise subprocess.CalledProcessError(1, ["ufw"], stderr="boom\n")


check(
    "main() exits 4 (not 0) when a delete fails partway through -- reported, not silent (TOCTOU Suggestion)",
    _run_main_with_stubs(ACTIVE_DEFAULT_DENY, MULTI_STALE, delete=_delete_fails) == 4,
)

# --- summary -----------------------------------------------------------------

if _failures:
    print("\n{} check(s) FAILED: {}".format(len(_failures), ", ".join(_failures)))
    sys.exit(1)
print("\nAll checks passed.")
sys.exit(0)
