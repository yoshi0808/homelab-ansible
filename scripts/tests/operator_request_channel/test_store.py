import json
import os
import shutil
import tempfile
import unittest

import _path_setup  # noqa: F401

from oprc import canonical, ids, store


def _make_spool(tmp_dir):
    for sub in ("inbox", "outbox", "events", "quarantine-metadata"):
        os.makedirs(os.path.join(tmp_dir, sub))
    return tmp_dir


def _put_message(spool_dir, box, request_id, message):
    meta = {
        "content_sha256": canonical.content_hash(message),
        "dlp_engine_version": "1",
        "dlp_ruleset_sha256": "f" * 64,
        "received_at": message.get("created_at", "2026-08-08T12:00:00+0900"),
        "source": "coordinator",
    }
    store.create_message(spool_dir, box, request_id, message, meta)
    return meta


class AtomicCreateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.spool = _make_spool(self.tmp.name)

    def test_create_then_read_back(self):
        rid = ids.generate_request_id()
        message = {"purpose": "x", "created_at": "2026-08-08T12:00:00+0900"}
        _put_message(self.spool, "inbox", rid, message)
        record = store.read_raw(self.spool, "inbox", rid)
        self.assertEqual(record["message"], message)

    def test_second_create_with_same_id_conflicts(self):
        rid = ids.generate_request_id()
        message_a = {"purpose": "first", "created_at": "2026-08-08T12:00:00+0900"}
        message_b = {"purpose": "second", "created_at": "2026-08-08T12:00:00+0900"}
        _put_message(self.spool, "inbox", rid, message_a)
        with self.assertRaises(store.StoreConflict):
            _put_message(self.spool, "inbox", rid, message_b)
        # First message must remain untouched (requirement §7.1).
        record = store.read_raw(self.spool, "inbox", rid)
        self.assertEqual(record["message"]["purpose"], "first")

    def test_message_file_mode_is_restrictive(self):
        rid = ids.generate_request_id()
        _put_message(self.spool, "inbox", rid, {"purpose": "x", "created_at": "2026-08-08T12:00:00+0900"})
        path = os.path.join(self.spool, "inbox", rid + ".json")
        mode = os.stat(path).st_mode & 0o777
        self.assertEqual(mode, 0o440)

    def test_invalid_request_id_is_rejected(self):
        with self.assertRaises(store.StoreError):
            store.create_message(self.spool, "inbox", "not-a-real-id", {}, {})

    def test_path_traversal_request_id_is_rejected(self):
        with self.assertRaises(store.StoreError):
            store.create_message(self.spool, "inbox", "../../etc/passwd", {}, {})

    def test_invalid_box_is_rejected(self):
        rid = ids.generate_request_id()
        with self.assertRaises(store.StoreError):
            store.create_message(self.spool, "sidebox", rid, {}, {})

    def test_read_missing_message_raises_not_found(self):
        with self.assertRaises(store.StoreNotFound):
            store.read_raw(self.spool, "inbox", ids.generate_request_id())


class EventTransitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.spool = _make_spool(self.tmp.name)
        self.rid = ids.generate_request_id()

    def _append(self, event_type):
        store.append_event(self.spool, self.rid, event_type, "2026-08-08T12:00:00+0900")

    def test_submitted_first_is_allowed(self):
        self._append("submitted")  # must not raise

    def test_accepted_before_submitted_is_rejected(self):
        with self.assertRaises(store.InvalidTransition):
            self._append("accepted")

    def test_submitted_then_accepted_then_answered_is_allowed(self):
        self._append("submitted")
        self._append("accepted")
        self._append("answered")  # must not raise

    def test_submitted_then_rejected_is_allowed(self):
        self._append("submitted")
        self._append("rejected")

    def test_answered_is_terminal(self):
        self._append("submitted")
        self._append("accepted")
        self._append("answered")
        with self.assertRaises(store.InvalidTransition):
            self._append("expired")

    def test_double_submitted_is_rejected(self):
        self._append("submitted")
        with self.assertRaises(store.InvalidTransition):
            self._append("submitted")

    def test_rejected_then_accepted_is_rejected(self):
        self._append("submitted")
        self._append("rejected")
        with self.assertRaises(store.InvalidTransition):
            self._append("accepted")

    def test_unknown_event_type_is_rejected(self):
        with self.assertRaises(store.StoreError):
            store.append_event(self.spool, self.rid, "bogus", "2026-08-08T12:00:00+0900")


class ReadMessageConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.spool = _make_spool(self.tmp.name)

    def _submitted(self, rid, message):
        _put_message(self.spool, "inbox", rid, message)
        store.append_event(self.spool, rid, "submitted", "2026-08-08T12:00:00+0900")

    def test_consistent_message_reads_cleanly(self):
        rid = ids.generate_request_id()
        message = {"purpose": "x", "created_at": "2026-08-08T12:00:00+0900"}
        self._submitted(rid, message)
        got_message, _meta, state = store.read_message(self.spool, "inbox", rid)
        self.assertEqual(got_message, message)
        self.assertEqual(state, "submitted")

    def test_message_without_events_is_inconsistent(self):
        rid = ids.generate_request_id()
        _put_message(self.spool, "inbox", rid, {"purpose": "x", "created_at": "2026-08-08T12:00:00+0900"})
        with self.assertRaises(store.StoreInconsistent):
            store.read_message(self.spool, "inbox", rid)

    def test_tampered_message_content_fails_hash_check(self):
        rid = ids.generate_request_id()
        message = {"purpose": "x", "created_at": "2026-08-08T12:00:00+0900"}
        self._submitted(rid, message)
        path = os.path.join(self.spool, "inbox", rid + ".json")
        # Simulate on-disk tampering directly (bypassing the library, which
        # never offers an update path) by rewriting the file's bytes.
        os.chmod(path, 0o600)
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        record["message"]["purpose"] = "tampered"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f)
        with self.assertRaises(store.StoreInconsistent):
            store.read_message(self.spool, "inbox", rid)

    def test_event_log_with_bad_json_line_is_inconsistent(self):
        rid = ids.generate_request_id()
        message = {"purpose": "x", "created_at": "2026-08-08T12:00:00+0900"}
        _put_message(self.spool, "inbox", rid, message)
        events_path = os.path.join(self.spool, "events", rid + ".jsonl")
        with open(events_path, "w", encoding="utf-8") as f:
            f.write("not json\n")
        with self.assertRaises(store.StoreInconsistent):
            store.read_message(self.spool, "inbox", rid)

    def test_event_log_with_wrong_request_id_is_inconsistent(self):
        rid = ids.generate_request_id()
        other_rid = ids.generate_request_id()
        message = {"purpose": "x", "created_at": "2026-08-08T12:00:00+0900"}
        _put_message(self.spool, "inbox", rid, message)
        events_path = os.path.join(self.spool, "events", rid + ".jsonl")
        with open(events_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"request_id": other_rid, "event": "submitted", "occurred_at": "x"}) + "\n")
        with self.assertRaises(store.StoreInconsistent):
            store.read_message(self.spool, "inbox", rid)

    def test_event_log_with_illegal_transition_is_inconsistent(self):
        rid = ids.generate_request_id()
        message = {"purpose": "x", "created_at": "2026-08-08T12:00:00+0900"}
        _put_message(self.spool, "inbox", rid, message)
        events_path = os.path.join(self.spool, "events", rid + ".jsonl")
        with open(events_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"request_id": rid, "event": "answered", "occurred_at": "x"}) + "\n")
        with self.assertRaises(store.StoreInconsistent):
            store.read_message(self.spool, "inbox", rid)


class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.spool = _make_spool(self.tmp.name)

    def test_within_limits_passes(self):
        store.check_capacity(self.spool, "inbox", max_messages=10, max_total_bytes=1_000_000, incoming_size=100)

    def test_message_count_limit_is_enforced(self):
        for _ in range(3):
            rid = ids.generate_request_id()
            _put_message(self.spool, "inbox", rid, {"purpose": "x", "created_at": "2026-08-08T12:00:00+0900"})
        with self.assertRaises(store.StoreCapacityExceeded):
            store.check_capacity(self.spool, "inbox", max_messages=3, max_total_bytes=1_000_000, incoming_size=1)

    def test_total_bytes_limit_is_enforced(self):
        rid = ids.generate_request_id()
        _put_message(self.spool, "inbox", rid, {"purpose": "x" * 100, "created_at": "2026-08-08T12:00:00+0900"})
        count, total = store.count_and_size(self.spool, "inbox")
        self.assertEqual(count, 1)
        with self.assertRaises(store.StoreCapacityExceeded):
            store.check_capacity(self.spool, "inbox", max_messages=10, max_total_bytes=total, incoming_size=1)

    def test_missing_box_directory_counts_as_empty(self):
        shutil.rmtree(os.path.join(self.spool, "outbox"))
        count, total = store.count_and_size(self.spool, "outbox")
        self.assertEqual((count, total), (0, 0))


class ListIdsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.spool = _make_spool(self.tmp.name)

    def _submitted(self, created_at):
        rid = ids.generate_request_id()
        message = {"purpose": "x", "created_at": created_at}
        _put_message(self.spool, "inbox", rid, message)
        store.append_event(self.spool, rid, "submitted", created_at)
        return rid

    def test_lists_in_created_at_order(self):
        rid_a = self._submitted("2026-08-08T09:00:00+0900")
        rid_b = self._submitted("2026-08-08T10:00:00+0900")
        rid_c = self._submitted("2026-08-08T08:00:00+0900")
        got, next_cursor, excluded = store.list_ids(self.spool, "inbox", cursor=None, page_size=50)
        self.assertEqual(got, [rid_c, rid_a, rid_b])
        self.assertIsNone(next_cursor)
        self.assertEqual(excluded, 0)

    def test_pagination_with_cursor(self):
        rids = [self._submitted("2026-08-08T{:02d}:00:00+0900".format(9 + i)) for i in range(5)]
        page1, cursor1, _ = store.list_ids(self.spool, "inbox", cursor=None, page_size=2)
        self.assertEqual(page1, rids[0:2])
        self.assertEqual(cursor1, rids[1])
        page2, cursor2, _ = store.list_ids(self.spool, "inbox", cursor=cursor1, page_size=2)
        self.assertEqual(page2, rids[2:4])
        self.assertEqual(cursor2, rids[3])
        page3, cursor3, _ = store.list_ids(self.spool, "inbox", cursor=cursor2, page_size=2)
        self.assertEqual(page3, rids[4:5])
        self.assertIsNone(cursor3)

    def test_invalid_cursor_is_rejected(self):
        with self.assertRaises(store.StoreError):
            store.list_ids(self.spool, "inbox", cursor="not-a-real-id", page_size=50)

    def test_inconsistent_entry_is_excluded_and_counted(self):
        good = self._submitted("2026-08-08T09:00:00+0900")
        # A message with no matching event -- inconsistent by construction.
        bad_rid = ids.generate_request_id()
        _put_message(self.spool, "inbox", bad_rid, {"purpose": "x", "created_at": "2026-08-08T09:30:00+0900"})
        got, _next_cursor, excluded = store.list_ids(self.spool, "inbox", cursor=None, page_size=50)
        self.assertEqual(got, [good])
        self.assertEqual(excluded, 1)

    def test_empty_box_returns_empty_page(self):
        got, next_cursor, excluded = store.list_ids(self.spool, "outbox", cursor=None, page_size=50)
        self.assertEqual(got, [])
        self.assertIsNone(next_cursor)
        self.assertEqual(excluded, 0)


class QuarantineAndAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.spool = _make_spool(self.tmp.name)

    def test_write_quarantine_round_trip(self):
        aid = ids.generate_attempt_id()
        record = {
            "attempt_id": aid,
            "occurred_at": "2026-08-08T12:00:00+0900",
            "source": "coordinator",
            "stage": "ansy_submit",
            "category": "pem_private_key",
            "pointer": "/purpose",
            "rule_id": "pem-or-ssh-private-key",
        }
        store.write_quarantine(self.spool, aid, record)
        path = os.path.join(self.spool, "quarantine-metadata", aid + ".json")
        with open(path, "r", encoding="utf-8") as f:
            got = json.load(f)
        self.assertEqual(got, record)

    def test_write_quarantine_rejects_invalid_attempt_id(self):
        with self.assertRaises(store.StoreError):
            store.write_quarantine(self.spool, "../etc/passwd", {})

    def test_append_audit_appends_lines(self):
        audit_path = os.path.join(self.tmp.name, "audit.jsonl")
        store.append_audit(audit_path, {"event": "one"})
        store.append_audit(audit_path, {"event": "two"})
        with open(audit_path, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f.readlines()]
        self.assertEqual(lines, [{"event": "one"}, {"event": "two"}])


if __name__ == "__main__":
    unittest.main()
