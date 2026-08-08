"""Regression test for deploy-verification 2026-08-08_010 item 1.

Real-world failure: quory's `inbox/` ACL granted `dev-investigate` only
`wx` (write+execute) on the directory, not `r`. `store.count_and_size()`
(called by `check_capacity()`, which every `submit` runs before
`create_message()`) calls `os.listdir()` to enumerate the box, which
requires directory-level `r` -- so every submit crashed with a
`PermissionError`, reproduced twice independently on the deployed host.
The fix (`roles/operator_request_channel/defaults/main.yml`) changed the
ACL to `rwx`; this test does not exercise that ACL fix directly (see
below), it guards the narrower design property the fix depends on.

Limitation (explicitly allowed by the task that requested this test):
this sandbox has no second OS user, so a real cross-uid permission
boundary cannot be reproduced here -- doing that would need a second uid,
which Implementer/Tester roles do not have. What this test proves instead
is a property of the *code path* itself: `count_and_size()` and
`check_capacity()` never call `open()` on an individual message file's
content -- only `os.listdir()` and `os.path.getsize()`. That property is
what makes granting directory-level `r` (without granting any read on the
message files themselves, which remain unreadable by `dev-investigate` --
see `defaults/main.yml`'s ACL comment) sufficient to fix the real bug
without reopening the "message body unreadable by the submitter" property
plan §2.3 requires.
"""

import os
import tempfile
import unittest
from unittest import mock

import _path_setup  # noqa: F401

from oprc import canonical, store


class CapacityCheckDoesNotReadMessageContentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name in ("inbox", "outbox", "events", "quarantine-metadata"):
            os.makedirs(os.path.join(self.tmp.name, name))
        for i in range(5):
            request_id = "req-20260808T0000{:02d}+0900-".format(i) + "a" * 16
            message = {"request_id": request_id, "n": i}
            meta = {"content_sha256": canonical.content_hash(message)}
            store.create_message(self.tmp.name, "inbox", request_id, message, meta)

    def _guarded_open(self, real_open):
        inbox_dir = os.path.join(self.tmp.name, "inbox")

        def guarded(path, *args, **kwargs):
            path_str = os.fspath(path)
            if path_str.startswith(inbox_dir) and path_str.endswith(".json"):
                raise AssertionError(
                    "must not open() a message file's content for a capacity check: {}".format(path_str)
                )
            return real_open(path, *args, **kwargs)

        return guarded

    def test_count_and_size_never_opens_message_file_content(self):
        real_open = open
        with mock.patch("builtins.open", side_effect=self._guarded_open(real_open)):
            count, total = store.count_and_size(self.tmp.name, "inbox")
        self.assertEqual(count, 5)
        self.assertGreater(total, 0)

    def test_check_capacity_never_opens_message_file_content(self):
        real_open = open
        with mock.patch("builtins.open", side_effect=self._guarded_open(real_open)):
            store.check_capacity(self.tmp.name, "inbox", max_messages=500, max_total_bytes=134217728, incoming_size=100)
        # must not raise

    def test_check_capacity_still_enforces_message_count_limit(self):
        # The re-confirmation condition is not just "doesn't crash" --
        # the limit itself must still be enforced once directory listing
        # works (which it now structurally always does in this test
        # fixture, matching the fixed ACL's effect).
        with self.assertRaises(store.StoreCapacityExceeded):
            store.check_capacity(self.tmp.name, "inbox", max_messages=5, max_total_bytes=134217728, incoming_size=1)

    def test_check_capacity_still_enforces_total_bytes_limit(self):
        _count, total = store.count_and_size(self.tmp.name, "inbox")
        with self.assertRaises(store.StoreCapacityExceeded):
            store.check_capacity(self.tmp.name, "inbox", max_messages=500, max_total_bytes=total, incoming_size=1)

    def test_check_capacity_passes_when_under_both_limits(self):
        store.check_capacity(self.tmp.name, "inbox", max_messages=500, max_total_bytes=134217728, incoming_size=1)
        # must not raise


if __name__ == "__main__":
    unittest.main()
