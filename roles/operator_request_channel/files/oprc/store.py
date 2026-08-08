"""Spool persistence: atomic message creation, append-only state events,
capacity limits, consistency-checked reads, cursor-based listing,
quarantine metadata, and audit log appends.

Layout (plan §2.2), rooted at a single `spool_dir`:

    <spool_dir>/inbox/<request_id>.json
    <spool_dir>/outbox/<request_id>.json
    <spool_dir>/events/<request_id>.jsonl
    <spool_dir>/quarantine-metadata/<attempt_id>.json

The audit log lives outside the spool (requirement §8) and is passed as
its own path (`audit_log_path`), not derived from `spool_dir`.

Stored message file shape: `{"message": {...}, "meta": {...}}`. `meta`
carries `content_sha256` (over `message`'s canonical JSON -- see
canonical.py), `dlp_engine_version`, `dlp_ruleset_sha256`, `received_at`,
`source`. The hash is *not* stored inside `message` itself, so hashing
`message` never has to special-case excluding its own hash field.

This module creates no directories -- `inbox/`, `outbox/`, `events/`,
`quarantine-metadata/` are expected to already exist with the owner/
group/mode/ACL the Ansible role sets up (plan §2.3). A missing directory
surfaces as a StoreError, not a silent mkdir.

Fail-closed reading (plan §2.9): any structural inconsistency between a
message file and its event file -- or within the event file itself --
raises `StoreInconsistent` instead of returning a partial or guessed
result. `list_ids()` instead *excludes* inconsistent entries from the page
and reports how many were excluded, so one damaged request does not take
the whole listing down (plan §2.9's stated tradeoff).
"""

import json
import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from . import canonical, ids

BOX_NAMES = ("inbox", "outbox")

# requirement §7.2's fixed vocabulary and the state machine it forms.
EVENT_TYPES = ("submitted", "accepted", "rejected", "answered", "expired")

ALLOWED_TRANSITIONS: Dict[Optional[str], "frozenset[str]"] = {
    None: frozenset({"submitted"}),
    "submitted": frozenset({"accepted", "rejected", "expired"}),
    "accepted": frozenset({"answered", "expired"}),
    "answered": frozenset(),
    "rejected": frozenset(),
    "expired": frozenset(),
}

_MESSAGE_FILE_MODE = 0o440
_EVENT_FILE_MODE = 0o640
_AUDIT_FILE_MODE = 0o660


class StoreError(Exception):
    """Base for all store failures. Callers must treat any subclass as
    fail-closed: do not proceed, do not guess, do not retry with relaxed
    checks."""


class StoreConflict(StoreError):
    """`request_id` already exists in this box (requirement §7.1: never
    overwrite on collision)."""


class StoreCapacityExceeded(StoreError):
    """Message count or total byte limit reached for this box
    (requirement §8: fail closed on new submit, do not evict old
    messages)."""


class StoreNotFound(StoreError):
    """No such `request_id` in this box."""


class StoreInconsistent(StoreError):
    """message/event data disagree with each other or are internally
    malformed (plan §2.9)."""


class InvalidTransition(StoreError):
    """The requested event type is not reachable from the current
    state."""


def _validate_request_id(request_id: str) -> None:
    # ids.py's regex already excludes "." and "/" structurally; this is a
    # second, independent check before the value ever touches a path,
    # matching the dispatcher's own multilayer-validation discipline
    # (recovery-investigate-dispatch-quory.sh validates, and so does the
    # helper it execs).
    if not ids.is_valid_request_id(request_id):
        raise StoreError("invalid request_id")
    if "/" in request_id or ".." in request_id:
        raise StoreError("invalid request_id")


def _box_dir(spool_dir: str, box: str) -> str:
    if box not in BOX_NAMES:
        raise StoreError("invalid box: {}".format(box))
    return os.path.join(spool_dir, box)


def _message_path(spool_dir: str, box: str, request_id: str) -> str:
    _validate_request_id(request_id)
    return os.path.join(_box_dir(spool_dir, box), request_id + ".json")


def _events_path(spool_dir: str, request_id: str) -> str:
    _validate_request_id(request_id)
    return os.path.join(spool_dir, "events", request_id + ".jsonl")


def _atomic_create(path: str, data: bytes, mode: int) -> None:
    """Create `path` containing exactly `data`, refusing to overwrite an
    existing file (whatever it is, including a symlink planted at that
    name) and refusing to write through a pre-existing symlink.

    Uses a temp file in the same directory plus `os.link()` (which fails
    with FileExistsError if the target name already exists) rather than
    `os.rename()` (which silently overwrites on POSIX). `os.link()` does
    not follow a symlink *at the target name* to overwrite whatever it
    points at -- it simply fails if that name is already occupied, by
    anything. This is requirement §8's "atomic rename または同等のatomic
    create" and "symlink／hardlink...を許可しない", together.
    """
    directory = os.path.dirname(path)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp-")
    except OSError as exc:
        raise StoreError("cannot create temp file in {}: {}".format(directory, type(exc).__name__))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_path, mode)
        try:
            os.link(tmp_path, path)
        except FileExistsError:
            raise StoreConflict("path already exists: {}".format(os.path.basename(path)))
        except OSError as exc:
            raise StoreError("cannot create {}: {}".format(path, type(exc).__name__))
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def count_and_size(spool_dir: str, box: str) -> Tuple[int, int]:
    """Return (message_count, total_bytes) for `box`. Missing directory
    counts as (0, 0) rather than raising -- callers that need the
    directory to exist find that out from `_atomic_create` when they try
    to write.

    Invariant callers rely on: this function must never `open()` a
    message file's content -- only `os.listdir()` (directory-level
    enumeration) and `os.path.getsize()` (metadata, not content). Some
    identities that call this (via `check_capacity()`, e.g. `oprc-
    receive` running as `dev-investigate` against `inbox/`) are granted
    directory-level read/traverse for exactly this capacity check, but
    are not granted -- and must not need -- read access to individual
    message files' content (`roles/operator_request_channel/defaults/
    main.yml`'s ACL design). If this function ever grows a reason to
    inspect a message's content, that reason does not belong here: do the
    read in a caller that is allowed to see message content, not in the
    shared capacity-counting path every box and every identity goes
    through. (2026-08-08: an ACL that only granted `wx`, not `r`, on
    `inbox/` made `os.listdir()` itself fail with `PermissionError` --
    see `docs/ai/reviews/operator_request_channel/
    2026-08-08_010_deploy_verification.md` item 1 -- which is why this
    property is now load-bearing enough to state explicitly instead of
    leaving it implicit in the code below.)
    """
    directory = _box_dir(spool_dir, box)
    try:
        names = os.listdir(directory)
    except FileNotFoundError:
        return 0, 0
    count = 0
    total = 0
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            total += os.path.getsize(os.path.join(directory, name))
        except OSError:
            continue
        count += 1
    return count, total


def check_capacity(spool_dir: str, box: str, max_messages: int, max_total_bytes: int, incoming_size: int) -> None:
    """Raise StoreCapacityExceeded if adding `incoming_size` bytes to `box`
    would exceed either limit. Call before `create_message()` -- this does
    not itself reserve space, so the caller's overall create path must
    still handle the (rare, benign) race of two concurrent submissions
    both passing this check and one losing to `StoreConflict` or slightly
    overshooting the byte total; the count/byte limits are a coarse
    fail-closed backstop, not a precise quota enforcement mechanism.
    """
    count, total = count_and_size(spool_dir, box)
    if count + 1 > max_messages:
        raise StoreCapacityExceeded("message count limit reached for {}".format(box))
    if total + incoming_size > max_total_bytes:
        raise StoreCapacityExceeded("total byte limit reached for {}".format(box))


def create_message(spool_dir: str, box: str, request_id: str, message: Dict[str, Any], meta: Dict[str, Any]) -> None:
    """Atomically create `<box>/<request_id>.json` containing
    `{"message": message, "meta": meta}`.

    Precondition: `meta["content_sha256"] == canonical.content_hash(message)`
    -- this function does not compute or check that itself (callers set
    `meta` up front, e.g. right after DLP passes), but `read_message()`
    re-verifies it on every read (requirement §7.1 "取得時に再照合する").

    Does not append the "submitted" event; callers do that as a separate
    `append_event()` call. A message that exists with no matching
    "submitted" event is exactly the inconsistency `read_message()` /
    `list_ids()` are built to catch, by design -- there is no path in this
    module that writes both atomically as one operation, so that failure
    mode has to be handled as data, not prevented by wishful thinking.
    """
    path = _message_path(spool_dir, box, request_id)
    record = {"message": message, "meta": meta}
    data = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    _atomic_create(path, data, _MESSAGE_FILE_MODE)


def read_raw(spool_dir: str, box: str, request_id: str) -> Dict[str, Any]:
    """Read `<box>/<request_id>.json` without any cross-checking against
    events. Most callers want `read_message()` instead; this is exposed
    for callers (or tests) that need the raw `{"message", "meta"}` record
    even when the caller intends to do its own consistency handling."""
    path = _message_path(spool_dir, box, request_id)
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        raise StoreNotFound(request_id)
    try:
        record = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise StoreInconsistent("message file is not valid JSON")
    if not isinstance(record, dict) or "message" not in record or "meta" not in record:
        raise StoreInconsistent("message file missing message/meta")
    return record


def append_event(spool_dir: str, request_id: str, event_type: str, occurred_at: str, extra: Optional[Dict[str, Any]] = None) -> None:
    """Append one state-transition event for `request_id`, refusing
    transitions the state machine (module-level `ALLOWED_TRANSITIONS`)
    does not allow.

    Uses a single `os.write()` call under `O_APPEND` to a per-request-id
    file, which is atomic with respect to other appenders on the same
    local filesystem -- this is what makes concurrent submits to
    *different* request_ids never interleave or lose an event (requirement
    §16); concurrent transitions on the *same* request_id are additionally
    serialized by the transition check below (a second writer re-reads the
    current state and finds its own transition no longer legal once the
    first writer's event is visible), though a true simultaneous
    read-then-write race between two processes is not fully closed by this
    module alone -- see the implement record's open items.
    """
    if event_type not in EVENT_TYPES:
        raise StoreError("unknown event type: {}".format(event_type))
    current = _current_state_unchecked(spool_dir, request_id)
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if event_type not in allowed:
        raise InvalidTransition("{} -> {} not allowed".format(current, event_type))

    path = _events_path(spool_dir, request_id)
    record: Dict[str, Any] = {"request_id": request_id, "event": event_type, "occurred_at": occurred_at}
    if extra:
        record["extra"] = extra
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"

    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, _EVENT_FILE_MODE)
    except OSError as exc:
        raise StoreError("cannot open event log: {}".format(type(exc).__name__))
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def _read_events_unchecked(spool_dir: str, request_id: str) -> List[Dict[str, Any]]:
    path = _events_path(spool_dir, request_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []
    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            raise StoreInconsistent("event line is not valid JSON")
        if not isinstance(record, dict) or record.get("request_id") != request_id:
            raise StoreInconsistent("event request_id mismatch")
        if record.get("event") not in EVENT_TYPES:
            raise StoreInconsistent("unknown event type in event log")
        events.append(record)
    return events


def _current_state_unchecked(spool_dir: str, request_id: str) -> Optional[str]:
    """Replay `request_id`'s event log and return the resulting state, or
    raise StoreInconsistent if the sequence contains an illegal
    transition. "unchecked" refers to not cross-checking against the
    message file -- the event sequence itself is always validated."""
    events = _read_events_unchecked(spool_dir, request_id)
    state: Optional[str] = None
    for record in events:
        event_type = record["event"]
        allowed = ALLOWED_TRANSITIONS.get(state, frozenset())
        if event_type not in allowed:
            raise StoreInconsistent("event log contains an illegal transition")
        state = event_type
    return state


def read_message(spool_dir: str, box: str, request_id: str) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """Read one message, verifying internal consistency before returning
    anything (plan §2.9):

    - the message file parses and has both `message` and `meta`
    - `meta["content_sha256"]` matches the recomputed hash of `message`
    - an event log exists and its first event is "submitted"
    - the event sequence is a legal state-machine path

    Returns `(message, meta, current_state)`. Raises `StoreNotFound` /
    `StoreInconsistent` rather than returning a partial result -- callers
    must not attempt to salvage a partial read, and must not print any
    part of `message` when re-raising to a human (requirement §16 "中途半
    端なmessageを可視化しないこと").
    """
    record = read_raw(spool_dir, box, request_id)
    message = record["message"]
    meta = record["meta"]
    expected_hash = meta.get("content_sha256") if isinstance(meta, dict) else None
    if not isinstance(expected_hash, str) or canonical.content_hash(message) != expected_hash:
        raise StoreInconsistent("content hash mismatch")

    events = _read_events_unchecked(spool_dir, request_id)
    if not events or events[0]["event"] != "submitted":
        raise StoreInconsistent("no submitted event")
    state = _current_state_unchecked(spool_dir, request_id)
    assert state is not None  # events is non-empty and starts with "submitted"
    return message, meta, state


def list_ids(spool_dir: str, box: str, cursor: Optional[str], page_size: int) -> Tuple[List[str], Optional[str], int]:
    """Return `(request_ids, next_cursor, excluded_count)` for one page,
    ordered by `(created_at, request_id)` ascending (plan §2.6).

    Entries that fail the consistency check are excluded from the result
    (not just this page -- every entry considered while building the
    sorted list is checked) rather than aborting the whole listing;
    `excluded_count` is the total number excluded among entries
    considered. `cursor`, when given, must itself be a syntactically valid
    request_id (plan §2.6: "検索式・条件式は受け取らない") -- an invalid
    cursor raises `StoreError` rather than being treated as "start from
    the beginning".
    """
    directory = _box_dir(spool_dir, box)
    try:
        names = os.listdir(directory)
    except FileNotFoundError:
        return [], None, 0

    entries: List[Tuple[str, str]] = []
    excluded = 0
    for name in names:
        if not name.endswith(".json"):
            continue
        request_id = name[: -len(".json")]
        if not ids.is_valid_request_id(request_id):
            excluded += 1
            continue
        try:
            message, _meta, _state = read_message(spool_dir, box, request_id)
        except StoreError:
            excluded += 1
            continue
        created_at = message.get("created_at", "")
        entries.append((created_at, request_id))

    entries.sort()

    if cursor is not None:
        if not ids.is_valid_request_id(cursor):
            raise StoreError("invalid cursor")
        start = None
        for i, (_, rid) in enumerate(entries):
            if rid == cursor:
                start = i + 1
                break
        entries = entries[start:] if start is not None else []

    page = entries[:page_size]
    next_cursor = page[-1][1] if len(entries) > page_size else None
    return [rid for _, rid in page], next_cursor, excluded


def write_quarantine(spool_dir: str, attempt_id: str, record: Dict[str, Any]) -> None:
    """Persist a rejected-payload record: category, JSON position, rule id,
    stage, source identity, timestamp -- never the payload itself
    (requirement §7.2, §9.4). `record` is the caller's responsibility to
    build without payload content; this function does not filter it."""
    if not ids.is_valid_attempt_id(attempt_id):
        raise StoreError("invalid attempt_id")
    path = os.path.join(spool_dir, "quarantine-metadata", attempt_id + ".json")
    data = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    _atomic_create(path, data, _MESSAGE_FILE_MODE)


def append_audit(audit_log_path: str, record: Dict[str, Any]) -> None:
    """Append one audit line to `audit_log_path` (outside the spool,
    requirement §8). Same single-`os.write()`-under-`O_APPEND` atomicity
    as `append_event()`. Caller is responsible for `record` containing no
    message body, content values, or DLP-detected strings (requirement
    §15) -- this function does not inspect or filter `record`.
    """
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    try:
        fd = os.open(audit_log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, _AUDIT_FILE_MODE)
    except OSError as exc:
        raise StoreError("cannot open audit log: {}".format(type(exc).__name__))
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)
