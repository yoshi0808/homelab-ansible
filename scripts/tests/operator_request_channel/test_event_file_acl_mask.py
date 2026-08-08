"""Regression test for the 2026-08-08 post-deploy vertical-test bug:
`accept-request` on quory failed with `error: unexpected internal failure
(StoreError)`, state stuck at `submitted`. `getfacl` on the real file
(Operator, quory) showed:

    user::rw-
    user:yoshi:rw-              #effective:r--
    user:dev-investigate:rw-    #effective:r--
    mask::r--
    group::---
    other::---

Root cause: when a directory has a default ACL and a *new* file is
created under it, the resulting ACL_MASK entry is capped by the **group**
permission bits of the `mode` argument passed to `open()`/`creat()` --
independent of what the directory's default ACL itself grants, and
independent of the file's own `group::` entry (inherited separately from
the directory's `default:group::`). `store._EVENT_FILE_MODE` was `0o640`
(group bits `r--`), which silently capped both named ACL grants
(`events/`'s default ACL grants `dev-investigate`/`yoshi` `rw`) down to an
effective `r--` -- exactly matching the `getfacl` output above. Fixed by
changing `_EVENT_FILE_MODE` to `0o660` (group bits `rw-`).

This module reproduces the mechanism directly with `setfacl`/`getfacl`
against a throwaway directory in this sandbox, shaped identically to the
real `events/`/`inbox/`/`outbox/`/`quarantine-metadata/` directories
(mode `1700`, a default ACL granting named users). No second real OS user
is needed to exercise the ACL mechanism itself -- an arbitrary numeric UID
is valid for a `setfacl` entry whether or not it maps to a real account,
and the mask-capping behavior operates purely at the filesystem level.

Also empirically confirms the "no other file class needs this fix" claim
(2026-08-08 review's re-confirmation condition) for `inbox`/`outbox`
message files, `quarantine-metadata`, and `audit.jsonl` -- each via the
same real setfacl/getfacl mechanism its actual deployment uses, not by
assertion.

**Follow-up (review 2026-08-08_013 Critical 1)**: fixing `_EVENT_FILE_MODE`
alone was not sufficient. `os.open()`'s `mode` argument is applied by the
kernel as `mode & ~umask`, so a calling process whose ambient umask strips
the group write bit (e.g. `022`) would still create the file at effective
`0o640` -- reproducing the exact same bug through a different variable
this module cannot observe on quory (an Operator session's umask is not
visible from ansy). `store.append_event()` was changed to fix the file's
mode explicitly via `os.fchmod()` after creation (never subject to
umask), mirroring `_atomic_create()`'s existing create-then-chmod pattern
for message files. `EventFileModeIsUmaskIndependentTests` below reproduces
this under a hostile umask via the real `store.append_event()` call (not
a hand-rolled `os.open()`), and
`AppendToExistingEventFileNeverAttemptsChmodTests` confirms the fix only
calls `os.fchmod()` when this process actually created the file --
calling it on a mere append to a file another identity created would
raise `EPERM` (chmod/fchmod require file ownership), which is exactly the
non-owning-append case this whole ACL design exists to support.
"""

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

import _path_setup  # noqa: F401

from oprc import store

# Arbitrary UIDs standing in for dev-investigate/yoshi -- do not need to
# resolve to real accounts on this machine (see module docstring).
_UID_A = 65533
_UID_B = 65534

_ACL_TOOLS_AVAILABLE = shutil.which("setfacl") is not None and shutil.which("getfacl") is not None


def _getfacl(path):
    result = subprocess.run(["getfacl", "-p", path], capture_output=True, text=True, check=True, timeout=5)
    return result.stdout


def _create(path, mode):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT, mode)
    os.close(fd)


@unittest.skipUnless(_ACL_TOOLS_AVAILABLE, "setfacl/getfacl not available in this environment")
class EventFileAclMaskTests(unittest.TestCase):
    """events/: both identities must be able to write to a file the other
    one created (submit's "submitted", the other identity's accept/
    reject/answered/expired) -- this is the one file class that actually
    needs the fix."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.chmod(self.tmp.name, 0o1700)  # matches events/'s real mode (plan §2.3)
        subprocess.run(
            ["setfacl", "-d", "-m", "u:{}:rw,u:{}:rw".format(_UID_A, _UID_B), self.tmp.name],
            check=True,
            timeout=5,
        )

    def test_the_actual_store_event_file_mode_is_not_capped_to_read_only(self):
        # Uses store._EVENT_FILE_MODE itself, not a hardcoded 0o660 --
        # if that constant ever regresses, this test fails.
        path = os.path.join(self.tmp.name, "event.jsonl")
        _create(path, store._EVENT_FILE_MODE)
        output = _getfacl(path)
        self.assertIn("mask::rw-", output, output)
        self.assertNotIn("#effective:r--", output, output)

    def test_old_buggy_mode_reproduces_the_capped_mask(self):
        # Documents the mechanism: 0o640's group bits (r--) cap the mask
        # to r-- regardless of the default ACL's own rw grant -- this is
        # literally what happened in production before the fix.
        path = os.path.join(self.tmp.name, "event_buggy.jsonl")
        _create(path, 0o640)
        output = _getfacl(path)
        self.assertIn("mask::r--", output, output)
        self.assertIn("#effective:r--", output, output)

    def test_fix_does_not_broaden_group_or_other(self):
        fixed_path = os.path.join(self.tmp.name, "event_fixed.jsonl")
        buggy_path = os.path.join(self.tmp.name, "event_buggy2.jsonl")
        _create(fixed_path, store._EVENT_FILE_MODE)
        _create(buggy_path, 0o640)
        fixed = _getfacl(fixed_path)
        buggy = _getfacl(buggy_path)

        def group_and_other(output):
            lines = [line for line in output.splitlines() if line.startswith("group::") or line.startswith("other::")]
            return lines

        # group:: and other:: come from the directory's own default ACL
        # entries (or lack thereof), never from the creation mode's bits
        # when a default ACL is present -- identical before and after.
        self.assertEqual(group_and_other(fixed), group_and_other(buggy))
        self.assertIn("other::---", fixed, fixed)
        self.assertIn("group::---", fixed, fixed)  # this sandbox's dir has no default:group:: entry


@unittest.skipUnless(_ACL_TOOLS_AVAILABLE, "setfacl/getfacl not available in this environment")
class OtherFileClassesDoNotNeedTheFixTests(unittest.TestCase):
    """2026-08-08 review's re-confirmation condition: confirm the same
    trap is not present elsewhere, without broadening anything that does
    not need it. inbox/outbox message files and quarantine-metadata are
    write-once (created once, never appended to by a second identity) and
    only ever need a second identity to *read* them -- `_MESSAGE_FILE_MODE`
    (`0o440`, group bits `r--`) is sufficient for that, verified the same
    way as the events/ case above."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.chmod(self.tmp.name, 0o1700)
        # Read-only grant, matching e.g. outbox's default ACL for
        # dev-investigate (rx on the dir, r as default on new files).
        subprocess.run(["setfacl", "-d", "-m", "u:{}:r".format(_UID_A), self.tmp.name], check=True, timeout=5)

    def test_message_file_mode_grants_exactly_the_read_access_it_needs(self):
        path = os.path.join(self.tmp.name, "msg.json")
        _create(path, store._MESSAGE_FILE_MODE)
        output = _getfacl(path)
        self.assertIn("mask::r--", output, output)
        # The named read-only grant is satisfied exactly (r <= mask r) --
        # no "#effective:" annotation appears when the effective
        # permission equals what was nominally granted.
        self.assertNotIn("#effective:", output, output)


@unittest.skipUnless(_ACL_TOOLS_AVAILABLE, "setfacl/getfacl not available in this environment")
class AuditLogUsesADifferentMechanismAndIsUnaffectedTests(unittest.TestCase):
    """audit.jsonl is pre-created by Ansible (`file: state=touch mode=0660`,
    roles/operator_request_channel/tasks/server.yml) *before* its ACL is
    applied via a direct `setfacl -m` on the already-existing file -- a
    different code path from "new file created under a directory's
    inherited default ACL" (the mechanism that caused the events/ bug).
    `setfacl -m` on an existing file recalculates the mask by default to
    accommodate the entries being added, so this file class was never
    exposed to the same trap. Confirmed here, not just asserted."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_setfacl_on_an_existing_0660_file_grants_full_effective_rw(self):
        path = os.path.join(self.tmp.name, "audit.jsonl")
        # Simulate Ansible's `file: state=touch mode=0660` (server.yml) --
        # created *before* any ACL exists, same as the real deployment.
        _create(path, 0o660)
        subprocess.run(
            ["setfacl", "-m", "u:{}:rw,u:{}:rw".format(_UID_A, _UID_B), path],
            check=True,
            timeout=5,
        )
        output = _getfacl(path)
        self.assertIn("mask::rw-", output, output)
        self.assertNotIn("#effective:r--", output, output)


@unittest.skipUnless(_ACL_TOOLS_AVAILABLE, "setfacl/getfacl not available in this environment")
class EventFileModeIsUmaskIndependentTests(unittest.TestCase):
    """review 2026-08-08_013 Critical 1: calls the real
    `store.append_event()` (not a hand-rolled `os.open()`) under a
    hostile umask (`022`, strips the group write bit) and checks the
    actual on-disk ACL result with `getfacl` -- proving the fix holds
    regardless of the calling process's umask, which is exactly the
    property requirement §8 ("作成時umaskと最終owner／group／modeを固定
    する") requires and which quory's Operator session umask (unobservable
    from ansy) made unsafe to simply measure-and-assume.

    Honest note on what this module could and could not reproduce: this
    implementer also tried to build a companion test proving that a
    *plain* `os.open(path, O_CREAT, mode)` (i.e. what `append_event()` did
    before the `os.fchmod()` fix) reproduces a capped `mask::r--` under
    the same hostile umask when `events/`'s default ACL is in play. On
    this sandbox's kernel (verified on both tmpfs and the repo's actual
    ext4 filesystem), it did not -- the resulting mask came out `rw-`
    regardless of umask in that specific case, even though a *plain* file
    with no default ACL involved was masked by umask exactly as expected
    (`0o660` under umask `022` -> `0o640`, verified separately). That
    means the interaction between umask and a directory's default ACL,
    specifically, is not something this sandbox could demonstrate going
    wrong -- but it is also not something documented as a cross-kernel
    guarantee, and quory's actual kernel cannot be inspected from here to
    confirm it behaves the same way. The fix does not depend on the
    answer either way: `os.fchmod()`'s exemption from umask is
    unconditional POSIX behavior (verified directly below, independent of
    ACLs entirely), which is why `append_event()` uses it rather than
    relying on how any particular kernel resolves the open()-vs-umask
    question for a default-ACL directory.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name in ("inbox", "outbox", "events", "quarantine-metadata"):
            os.makedirs(os.path.join(self.tmp.name, name))
        events_dir = os.path.join(self.tmp.name, "events")
        os.chmod(events_dir, 0o1700)  # matches events/'s real mode (plan §2.3)
        subprocess.run(
            ["setfacl", "-d", "-m", "u:{}:rw,u:{}:rw".format(_UID_A, _UID_B), events_dir],
            check=True,
            timeout=5,
        )
        # The hostile condition itself: a umask that strips the group
        # write bit, exactly like the one Critical 1 warned quory's
        # Operator session might have. Restored unconditionally after
        # each test -- umask is process-global, so leaking a changed
        # value would affect every other test in this process.
        old_umask = os.umask(0o022)
        self.addCleanup(os.umask, old_umask)

    def test_append_event_fixes_the_mode_even_under_a_hostile_umask(self):
        request_id = "req-20260808T000020+0900-" + "a" * 16
        store.append_event(self.tmp.name, request_id, "submitted", "2026-08-08T12:00:00+0900")
        path = os.path.join(self.tmp.name, "events", request_id + ".jsonl")
        output = _getfacl(path)
        self.assertIn("mask::rw-", output, output)
        self.assertNotIn("#effective:r--", output, output)

    def test_umask_masks_a_plain_open_with_no_default_acl_involved(self):
        # Sanity check that umask 022 is genuinely active and doing what
        # umask normally does in this process -- rules out "umask silently
        # had no effect at all in this sandbox" as an explanation for the
        # class docstring's finding above, by exercising the traditional
        # (non-ACL) case where masking is unambiguous and well documented.
        plain_dir = os.path.join(self.tmp.name, "no_default_acl")
        os.makedirs(plain_dir)
        path = os.path.join(plain_dir, "plain.txt")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o660)
        os.close(fd)
        mode = stat.S_IMODE(os.stat(path).st_mode)
        self.assertEqual(oct(mode), oct(0o640), "umask 022 should strip the group write bit here")

    def test_fchmod_is_exempt_from_umask_unconditionally(self):
        # The property the fix actually depends on -- independent of ACLs,
        # default ACLs, or any kernel-specific open()-vs-umask resolution.
        path = os.path.join(self.tmp.name, "fchmod_target.txt")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
        try:
            os.fchmod(fd, 0o660)
        finally:
            os.close(fd)
        mode = stat.S_IMODE(os.stat(path).st_mode)
        self.assertEqual(oct(mode), oct(0o660), "os.fchmod() must not be masked by umask")


class AppendToExistingEventFileNeverAttemptsChmodTests(unittest.TestCase):
    """The `os.fchmod()` fix must only fire on the branch that actually
    created the file. Calling it when merely appending to a file a
    *different* identity created would raise `EPERM` (chmod/fchmod
    require file ownership) -- exactly the non-owning-append case this
    whole per-request events/ file exists to support (dev-investigate and
    yoshi routinely append to files the other one created). This sandbox
    has only one real uid, so it cannot reproduce `EPERM` directly;
    instead it verifies the code-level guarantee the EPERM-avoidance
    depends on: `os.fchmod()` is called exactly once, for the creating
    call, never again on a subsequent append to the same file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.makedirs(os.path.join(self.tmp.name, "events"))

    def test_fchmod_is_called_only_when_creating_not_on_a_later_append(self):
        request_id = "req-20260808T000021+0900-" + "b" * 16
        with mock.patch("os.fchmod", wraps=os.fchmod) as mock_fchmod:
            store.append_event(self.tmp.name, request_id, "submitted", "2026-08-08T12:00:00+0900")
            self.assertEqual(mock_fchmod.call_count, 1)
            store.append_event(self.tmp.name, request_id, "accepted", "2026-08-08T12:00:01+0900")
            self.assertEqual(mock_fchmod.call_count, 1, "fchmod must not be attempted again on an append to an existing file")
            store.append_event(self.tmp.name, request_id, "answered", "2026-08-08T12:00:02+0900")
            self.assertEqual(mock_fchmod.call_count, 1)


if __name__ == "__main__":
    unittest.main()
