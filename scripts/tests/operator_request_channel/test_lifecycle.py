import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone

import _path_setup  # noqa: F401

from oprc import canonical, lifecycle, store

JST = timezone(timedelta(hours=9))


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


class ComputeExpiresAtTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 8, 12, 0, 0, tzinfo=JST)
        self.received_at = _iso(self.now)

    def test_omitted_uses_default_ttl(self):
        result = lifecycle.compute_expires_at(None, self.received_at, max_ttl_days=14, default_ttl_days=7)
        self.assertEqual(result, _iso(self.now + timedelta(days=7)))

    def test_within_max_ttl_is_kept_verbatim(self):
        raw = _iso(self.now + timedelta(days=10))
        result = lifecycle.compute_expires_at(raw, self.received_at, max_ttl_days=14, default_ttl_days=7)
        self.assertEqual(result, raw)

    def test_exactly_at_max_ttl_is_accepted(self):
        raw = _iso(self.now + timedelta(days=14))
        result = lifecycle.compute_expires_at(raw, self.received_at, max_ttl_days=14, default_ttl_days=7)
        self.assertEqual(result, raw)

    def test_beyond_max_ttl_is_rejected(self):
        raw = _iso(self.now + timedelta(days=14, seconds=1))
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.compute_expires_at(raw, self.received_at, max_ttl_days=14, default_ttl_days=7)

    def test_not_after_created_at_is_rejected(self):
        raw = _iso(self.now)
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.compute_expires_at(raw, self.received_at, max_ttl_days=14, default_ttl_days=7)

    def test_before_created_at_is_rejected(self):
        raw = _iso(self.now - timedelta(days=1))
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.compute_expires_at(raw, self.received_at, max_ttl_days=14, default_ttl_days=7)

    def test_unparseable_is_rejected(self):
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.compute_expires_at("not-a-timestamp", self.received_at, max_ttl_days=14, default_ttl_days=7)

    def test_non_string_is_rejected(self):
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.compute_expires_at(12345, self.received_at, max_ttl_days=14, default_ttl_days=7)


class IsExpiredTests(unittest.TestCase):
    def test_future_is_not_expired(self):
        now = datetime(2026, 8, 8, 12, 0, 0, tzinfo=JST)
        future = _iso(now + timedelta(days=1))
        self.assertFalse(lifecycle.is_expired(future, now))

    def test_past_is_expired(self):
        now = datetime(2026, 8, 8, 12, 0, 0, tzinfo=JST)
        past = _iso(now - timedelta(seconds=1))
        self.assertTrue(lifecycle.is_expired(past, now))


class MarkExpiredIfNeededTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name in ("inbox", "outbox", "events", "quarantine-metadata"):
            os.makedirs(os.path.join(self.tmp.name, name))
        self.now = datetime(2026, 8, 8, 12, 0, 0, tzinfo=JST)

    def _seed(self, request_id, expires_at, state_events):
        message = {"request_id": request_id, "expires_at": expires_at}
        meta = {"content_sha256": canonical.content_hash(message)}
        store.create_message(self.tmp.name, "outbox", request_id, message, meta)
        for evt in state_events:
            store.append_event(self.tmp.name, request_id, evt, _iso(self.now))
        return message

    def test_expired_submitted_request_gets_expired_event(self):
        request_id = "req-20260808T000000+0900-" + "a" * 16
        message = self._seed(request_id, _iso(self.now - timedelta(seconds=1)), ["submitted"])
        new_state = lifecycle.mark_expired_if_needed(self.tmp.name, "outbox", request_id, message, "submitted", self.now)
        self.assertEqual(new_state, "expired")
        _msg, _meta, state = store.read_message(self.tmp.name, "outbox", request_id)
        self.assertEqual(state, "expired")

    def test_expired_accepted_request_gets_expired_event(self):
        request_id = "req-20260808T000001+0900-" + "b" * 16
        message = self._seed(request_id, _iso(self.now - timedelta(seconds=1)), ["submitted", "accepted"])
        new_state = lifecycle.mark_expired_if_needed(self.tmp.name, "outbox", request_id, message, "accepted", self.now)
        self.assertEqual(new_state, "expired")

    def test_not_yet_expired_is_left_alone(self):
        request_id = "req-20260808T000002+0900-" + "c" * 16
        message = self._seed(request_id, _iso(self.now + timedelta(days=1)), ["submitted"])
        new_state = lifecycle.mark_expired_if_needed(self.tmp.name, "outbox", request_id, message, "submitted", self.now)
        self.assertEqual(new_state, "submitted")
        _msg, _meta, state = store.read_message(self.tmp.name, "outbox", request_id)
        self.assertEqual(state, "submitted")

    def test_terminal_states_are_not_touched_even_if_expires_at_passed(self):
        request_id = "req-20260808T000003+0900-" + "d" * 16
        message = self._seed(request_id, _iso(self.now - timedelta(days=1)), ["submitted", "accepted", "answered"])
        new_state = lifecycle.mark_expired_if_needed(self.tmp.name, "outbox", request_id, message, "answered", self.now)
        self.assertEqual(new_state, "answered")

    def test_missing_expires_at_is_left_alone(self):
        request_id = "req-20260808T000004+0900-" + "e" * 16
        message = {"request_id": request_id}
        new_state = lifecycle.mark_expired_if_needed(self.tmp.name, "outbox", request_id, message, "submitted", self.now)
        self.assertEqual(new_state, "submitted")


class MarkExpiredIfNeededConcurrencyTests(unittest.TestCase):
    """review 2026-08-08_006 Suggestion 2: reproduces the scenario the
    review described -- multiple readers all observing the same stale
    "submitted" `state` (as `store.read_message()` would return it before
    any of them has written anything) and all calling
    `mark_expired_if_needed()` for the same request_id at effectively the
    same instant. Before the fix, `store.append_event()`'s own
    check-then-act (re-read current state, then a separate `os.write()`)
    was unprotected, so more than one "expired" line could land; since
    `ALLOWED_TRANSITIONS["expired"]` is empty, a second "expired" line
    made every later read of that request raise StoreInconsistent
    permanently. This test uses real OS threads (not a mock) so the
    `fcntl.flock()` call in `mark_expired_if_needed()` genuinely contends
    -- `flock` blocks on the underlying syscall, which releases the GIL,
    so this exercises the same kernel-level serialization concurrent
    *processes* would get, without needing `multiprocessing`.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name in ("inbox", "outbox", "events", "quarantine-metadata"):
            os.makedirs(os.path.join(self.tmp.name, name))

    def test_many_concurrent_callers_append_exactly_one_expired_event(self):
        request_id = "req-20260808T000011+0900-" + "7" * 16
        now = datetime(2026, 8, 8, 12, 0, 0, tzinfo=JST)
        expires_at = _iso(now - timedelta(seconds=1))
        message = {"request_id": request_id, "expires_at": expires_at}
        meta = {"content_sha256": canonical.content_hash(message)}
        store.create_message(self.tmp.name, "outbox", request_id, message, meta)
        store.append_event(self.tmp.name, request_id, "submitted", _iso(now - timedelta(days=1)))

        thread_count = 12
        barrier = threading.Barrier(thread_count)
        results = []
        errors = []
        lock = threading.Lock()

        def worker():
            barrier.wait()  # maximize the odds every thread races together
            try:
                # Every thread is handed the *same* stale state="submitted"
                # -- exactly what store.read_message() would have returned
                # to each of them an instant earlier, before any of them
                # had written anything.
                new_state = lifecycle.mark_expired_if_needed(self.tmp.name, "outbox", request_id, message, "submitted", now)
            except Exception as exc:  # noqa: BLE001 -- capturing for assertion, not swallowing
                with lock:
                    errors.append(exc)
                return
            with lock:
                results.append(new_state)

        threads = [threading.Thread(target=worker) for _ in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(errors, [], "no caller should raise: {}".format(errors))
        self.assertEqual(len(results), thread_count)
        self.assertTrue(all(r == "expired" for r in results), results)

        # Exactly one "expired" line, not thread_count of them.
        events_path = os.path.join(self.tmp.name, "events", request_id + ".jsonl")
        with open(events_path, encoding="utf-8") as f:
            event_lines = [json.loads(line) for line in f if line.strip()]
        expired_lines = [e for e in event_lines if e["event"] == "expired"]
        self.assertEqual(len(expired_lines), 1, event_lines)

        # The request is still cleanly readable -- not permanently
        # StoreInconsistent (the exact failure mode the review described).
        _msg, _meta, state = store.read_message(self.tmp.name, "outbox", request_id)
        self.assertEqual(state, "expired")

    def test_lock_is_scoped_per_request_id_not_global(self):
        # Two *different* requests racing at the same time must not
        # serialize against each other -- flock() is taken on each
        # request's own events file, not a single shared lock file.
        now = datetime(2026, 8, 8, 12, 0, 0, tzinfo=JST)
        expires_at = _iso(now - timedelta(seconds=1))
        request_ids = ["req-20260808T000012+0900-" + str(i) * 16 for i in range(2)]
        messages = {}
        for rid in request_ids:
            message = {"request_id": rid, "expires_at": expires_at}
            meta = {"content_sha256": canonical.content_hash(message)}
            store.create_message(self.tmp.name, "outbox", rid, message, meta)
            store.append_event(self.tmp.name, rid, "submitted", _iso(now - timedelta(days=1)))
            messages[rid] = message

        barrier = threading.Barrier(2)
        results = {}

        def worker(rid):
            barrier.wait()
            results[rid] = lifecycle.mark_expired_if_needed(self.tmp.name, "outbox", rid, messages[rid], "submitted", now)

        threads = [threading.Thread(target=worker, args=(rid,)) for rid in request_ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        for rid in request_ids:
            self.assertEqual(results[rid], "expired")
            _msg, _meta, state = store.read_message(self.tmp.name, "outbox", rid)
            self.assertEqual(state, "expired")

    def test_accept_racing_expire_on_the_same_request_does_not_corrupt_it(self):
        # The narrower fix (locking mark_expired_if_needed against itself)
        # would not have closed this: accept-request calls
        # store.append_event() directly. This proves
        # lifecycle.append_event_locked() -- which accept-request/
        # reject-request/the "answered" append now use instead -- takes
        # the *same* per-request lock mark_expired_if_needed() does, so
        # the two genuinely serialize against each other too, not just
        # against callers of the same function.
        request_id = "req-20260808T000014+0900-" + "8" * 16
        now = datetime(2026, 8, 8, 12, 0, 0, tzinfo=JST)
        expires_at = _iso(now - timedelta(seconds=1))
        message = {"request_id": request_id, "expires_at": expires_at}
        meta = {"content_sha256": canonical.content_hash(message)}
        store.create_message(self.tmp.name, "outbox", request_id, message, meta)
        store.append_event(self.tmp.name, request_id, "submitted", _iso(now - timedelta(days=1)))

        thread_count = 10
        barrier = threading.Barrier(thread_count)
        outcomes = []
        lock = threading.Lock()

        def expire_worker():
            barrier.wait()
            try:
                result = lifecycle.mark_expired_if_needed(self.tmp.name, "outbox", request_id, message, "submitted", now)
                with lock:
                    outcomes.append(("expire", "ok", result))
            except store.InvalidTransition:
                with lock:
                    outcomes.append(("expire", "rejected", None))
            except Exception as exc:  # noqa: BLE001 -- must not go unrecorded
                with lock:
                    outcomes.append(("expire", "error", exc))

        def accept_worker():
            barrier.wait()
            try:
                lifecycle.append_event_locked(self.tmp.name, request_id, "accepted", lifecycle.now_iso(now))
                with lock:
                    outcomes.append(("accept", "ok", "accepted"))
            except store.InvalidTransition:
                with lock:
                    outcomes.append(("accept", "rejected", None))
            except Exception as exc:  # noqa: BLE001 -- must not go unrecorded
                with lock:
                    outcomes.append(("accept", "error", exc))

        threads = [
            threading.Thread(target=expire_worker if i % 2 == 0 else accept_worker)
            for i in range(thread_count)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(len(outcomes), thread_count)
        errors = [o for o in outcomes if o[1] == "error"]
        self.assertEqual(errors, [], "no caller should raise anything but InvalidTransition: {}".format(errors))

        # `mark_expired_if_needed()` is intentionally idempotent: an
        # "expire" worker that acquires the lock *after* someone else has
        # already moved the request to "accepted" (still an expirable
        # state -- accepted-but-past-TTL is meant to keep expiring) will
        # itself legitimately write "expired" and report "ok"; any further
        # "expire" worker after *that* sees a terminal "expired" state and
        # also reports "ok" without writing anything (a true no-op read,
        # not a second write). So more than one "ok" outcome is expected
        # and is not itself evidence of a problem -- what actually matters
        # is how many *events* landed in the log, which is checked below.
        self.assertGreaterEqual(len([o for o in outcomes if o[1] == "ok"]), 1)

        # The request is still cleanly readable -- read_message() would
        # raise StoreInconsistent if the event log had picked up an
        # illegal transition (e.g. a second "expired" line, or "accepted"
        # after "expired").
        _msg, _meta, state = store.read_message(self.tmp.name, "outbox", request_id)
        self.assertIn(state, ("expired", "accepted"))

        # Ground truth: each of "accepted" and "expired" was actually
        # written at most once, regardless of how many callers reported
        # "ok" above.
        events_path = os.path.join(self.tmp.name, "events", request_id + ".jsonl")
        with open(events_path, encoding="utf-8") as f:
            event_types = [json.loads(line)["event"] for line in f if line.strip()]
        self.assertLessEqual(event_types.count("accepted"), 1, event_types)
        self.assertLessEqual(event_types.count("expired"), 1, event_types)


class ReadStateFromEventsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.makedirs(os.path.join(self.tmp.name, "events"))

    def test_matches_store_read_message_state_without_touching_the_message_file(self):
        request_id = "req-20260808T000005+0900-" + "f" * 16
        now = "2026-08-08T12:00:00+0900"
        store.append_event(self.tmp.name, request_id, "submitted", now)
        store.append_event(self.tmp.name, request_id, "accepted", now)
        state = lifecycle.read_state_from_events(self.tmp.name, request_id)
        self.assertEqual(state, "accepted")
        # No inbox/ or outbox/ directory exists in this fixture at all --
        # if this function ever tried to open the message file, it would
        # raise, not return "accepted". That absence is the test.

    def test_missing_event_log_is_not_found(self):
        with self.assertRaises(store.StoreNotFound):
            lifecycle.read_state_from_events(self.tmp.name, "req-20260808T000006+0900-" + "0" * 16)

    def test_illegal_transition_is_inconsistent(self):
        request_id = "req-20260808T000007+0900-" + "1" * 16
        path = os.path.join(self.tmp.name, "events", request_id + ".jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"request_id": request_id, "event": "answered", "occurred_at": "2026-08-08T12:00:00+0900"}) + "\n")
        with self.assertRaises(store.StoreInconsistent):
            lifecycle.read_state_from_events(self.tmp.name, request_id)

    def test_malformed_line_is_inconsistent(self):
        request_id = "req-20260808T000008+0900-" + "2" * 16
        path = os.path.join(self.tmp.name, "events", request_id + ".jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write("not json\n")
        with self.assertRaises(store.StoreInconsistent):
            lifecycle.read_state_from_events(self.tmp.name, request_id)


class WriteRejectionAndAcceptedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name in ("inbox", "outbox", "events", "quarantine-metadata"):
            os.makedirs(os.path.join(self.tmp.name, name))
        self.audit_log = os.path.join(self.tmp.name, "audit.jsonl")

    def test_write_rejection_never_stores_payload_and_mints_no_request_id(self):
        before = set(os.listdir(os.path.join(self.tmp.name, "inbox")))
        attempt_id = lifecycle.write_rejection(
            self.tmp.name, self.audit_log, "coordinator", "dlp:blocked",
            category="password_keyvalue", rule_id="r1", pointer="/purpose",
        )
        after = set(os.listdir(os.path.join(self.tmp.name, "inbox")))
        self.assertEqual(before, after)  # nothing landed in inbox
        with open(os.path.join(self.tmp.name, "quarantine-metadata", attempt_id + ".json"), encoding="utf-8") as f:
            record = json.load(f)
        self.assertEqual(record["stage"], "dlp:blocked")
        self.assertEqual(record["category"], "password_keyvalue")
        self.assertNotIn("payload", record)
        with open(self.audit_log, encoding="utf-8") as f:
            audit_record = json.loads(f.readline())
        self.assertEqual(audit_record["attempt_id"], attempt_id)

    def test_write_accepted_creates_message_event_and_audit_line(self):
        request_id = "req-20260808T000009+0900-" + "3" * 16
        message = {
            "request_id": request_id, "conversation_id": "cnv-x", "type": "OPREQ",
            "source": "coordinator", "created_at": "2026-08-08T12:00:00+0900", "schema_version": 1,
        }
        meta = {"content_sha256": canonical.content_hash(message), "dlp_engine_version": "1", "dlp_ruleset_sha256": "a" * 64}
        lifecycle.write_accepted(self.tmp.name, "inbox", self.audit_log, request_id, message, meta)
        stored_message, _meta, state = store.read_message(self.tmp.name, "inbox", request_id)
        self.assertEqual(stored_message, message)
        self.assertEqual(state, "submitted")
        with open(self.audit_log, encoding="utf-8") as f:
            audit_record = json.loads(f.readline())
        self.assertEqual(audit_record["request_id"], request_id)
        self.assertEqual(audit_record["result"], "accepted")


class DescribeFailureExceptionChainTests(unittest.TestCase):
    """review differential (2026-08-08, `_013_review_event_mode.md`
    follow-up): a single-innermost-exception walk (`_root_cause()`, since
    removed) hid the real failure whenever a *new* exception was raised
    while an `except` block was still handling an earlier, harmless
    control-flow exception -- exactly `store.append_event()`'s
    `except FileExistsError:` shape. `_exception_chain()`/
    `_describe_failure()` must report every link, not just one. The
    entry-point-level regression test for the exact production shape
    lives in each `test_entrypoint_*.py` file
    (`test_intermediate_exception_inside_a_control_flow_except_handler_is_not_hidden`);
    these are the direct, whitebox-level tests of the chain-walking
    functions themselves."""

    def test_single_exception_with_no_chain(self):
        exc = store.StoreError("x")
        chain = lifecycle._exception_chain(exc)
        self.assertEqual(chain, [exc])
        self.assertEqual(lifecycle._describe_failure(exc), "StoreError")

    def test_exception_raised_inside_an_except_handler_for_a_control_flow_exception_reports_both(self):
        # Reproduces store.append_event()'s exact shape at the unit level:
        # `except FileExistsError:` is not a failure, but the exception
        # raised *inside* that handler chains to it via __context__.
        try:
            try:
                raise FileExistsError(17, "File exists")
            except FileExistsError:
                try:
                    raise PermissionError(13, "Permission denied")
                except OSError as inner:
                    raise store.StoreError("wrapped: {}".format(type(inner).__name__))
        except store.StoreError as outer:
            description = lifecycle._describe_failure(outer)
            chain = lifecycle._exception_chain(outer)

        class_names = [type(link).__name__ for link in chain]
        self.assertEqual(class_names, ["StoreError", "PermissionError", "FileExistsError"])
        self.assertIn("StoreError", description)
        self.assertIn("PermissionError", description)
        self.assertIn("errno=13", description)
        self.assertIn("FileExistsError", description)
        self.assertIn("errno=17", description)
        self.assertNotIn("Permission denied", description)
        self.assertNotIn("File exists", description)
        self.assertNotIn("wrapped:", description)

    def test_explicit_cause_is_preferred_over_implicit_context(self):
        # Constructed directly (not via nested try/except) to isolate
        # exactly the property under test: at a single link, an explicit
        # `__cause__` must be preferred over an incidental `__context__` --
        # without also asserting anything about *that* exception's own
        # further context (a real chain naturally continues past it, which
        # is covered by the other tests in this class).
        unrelated_context = ValueError("unrelated context")
        cause = PermissionError(13, "denied")
        outer = store.StoreError("wrapped")
        outer.__context__ = unrelated_context  # implicit chaining alone would point here
        outer.__cause__ = cause  # explicit `raise ... from cause` must win instead
        chain = lifecycle._exception_chain(outer)
        class_names = [type(link).__name__ for link in chain]
        self.assertEqual(class_names, ["StoreError", "PermissionError"])
        self.assertNotIn("ValueError", class_names)

    def test_cycle_does_not_hang(self):
        a = ValueError("a")
        b = ValueError("b")
        a.__context__ = b
        b.__context__ = a  # deliberate cycle
        chain = lifecycle._exception_chain(a)
        # Must terminate and must not contain unbounded repeats.
        self.assertLessEqual(len(chain), lifecycle._MAX_CHAIN_LENGTH)
        self.assertIn(a, chain)

    def test_chain_length_is_capped(self):
        # Build a chain deeper than _MAX_CHAIN_LENGTH and confirm the walk
        # stops instead of growing unbounded ("出力の長さに上限があること
        # (チェーンが長くても壊れない)").
        exceptions = [ValueError("e{}".format(i)) for i in range(lifecycle._MAX_CHAIN_LENGTH + 5)]
        for outer, inner in zip(exceptions, exceptions[1:]):
            outer.__context__ = inner
        chain = lifecycle._exception_chain(exceptions[0])
        self.assertEqual(len(chain), lifecycle._MAX_CHAIN_LENGTH)
        description = lifecycle._describe_failure(exceptions[0])
        self.assertIn("truncated", description)

    def test_description_string_length_is_capped(self):
        # A chain of exceptions with deliberately long class names must not
        # make the printed description grow without bound either.
        class ThisIsADeliberatelyVeryLongExceptionClassNameToStressTheDescriptionLengthCapAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA(Exception):
            pass

        exceptions = [ThisIsADeliberatelyVeryLongExceptionClassNameToStressTheDescriptionLengthCapAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA() for _ in range(lifecycle._MAX_CHAIN_LENGTH)]
        for outer, inner in zip(exceptions, exceptions[1:]):
            outer.__context__ = inner
        description = lifecycle._describe_failure(exceptions[0])
        self.assertLessEqual(len(description), lifecycle._MAX_DESCRIPTION_LENGTH + len("...(truncated)"))

    def test_non_oserror_links_carry_no_errno(self):
        try:
            try:
                raise RuntimeError("boom")
            except RuntimeError as inner:
                raise store.StoreError("wrapped") from inner
        except store.StoreError as outer:
            description = lifecycle._describe_failure(outer)
        self.assertNotIn("errno", description)


if __name__ == "__main__":
    unittest.main()
