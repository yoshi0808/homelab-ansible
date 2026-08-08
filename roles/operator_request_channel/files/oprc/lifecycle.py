"""Entry-point-layer lifecycle decisions the shared library (canonical /
config / dlp / ids / schema / store) deliberately left open, per the
implement record for the library layer
(docs/ai/reviews/operator_request_channel/2026-08-08_004_implement_core.md
§6 items 2 and 3):

1. `expires_at` bound enforcement (requirement §6.1: "expires_at は固定
   された最大TTLを超えてはならない") -- `compute_expires_at()`.
2. Deciding when a request becomes `expired` (requirement §7.2 lists
   `expired` as a valid state; nothing in store.py decides when to mint
   it) -- `mark_expired_if_needed()` / `read_state_from_events()`.

This is a **new** file in the shared `oprc/` package, not a modification
of anything the library-layer Implementer wrote (canonical.py / config.py
/ dlp.py / ids.py / schema.py / store.py / wire.py are untouched). It
lives here rather than being duplicated across
bin/operator-channel-client, bin/oprc-receive and bin/operator-channel
because plan §2.1 wants those three entry points to stay thin ("呼び出し
順だけを持つ") -- decision logic, even entry-point-owned decision logic,
belongs in a library module.

Design decision -- lazy, observed-on-read expiry: nothing in this MVP runs
a periodic sweep. A request's `expired` event is appended the next time
some quory-side process with read access to its message happens to read
it (list-pending, show-request, show-status, outbox request-status, ...)
and notices `now > expires_at` while the state is still `submitted` or
`accepted`. Requirement §17 excludes new daemons/services from this MVP;
a lazy check piggybacked on existing reads needs none, and requirement
§5.4 already establishes that "request登録だけでOperatorセッション...を
自動起動しない" -- nothing here was going to notice unattended expiry
sooner regardless of how `expired` gets minted. The tradeoff, stated
plainly: a request nobody has looked at since its TTL passed keeps
reporting its last real state until someone with read access looks.
Judged acceptable for an MVP; see the implement record for the fuller
rationale and what would change this.

Concurrent expiry marking is serialized per request_id via an advisory
`flock` on that request's own events file (`mark_expired_if_needed()`'s
own docstring has the full reasoning; review 2026-08-08_006 Suggestion
2). This still touches no file store.py does not already touch, and adds
no new file to the spool layout.

`read_state_from_events()` exists because `oprc-receive`'s `request-status`
on an *inbox* item (an OPREQ ansy itself submitted) only ever needs to
answer "what state is this request in" -- a question `events/<id>.jsonl`
alone answers exactly, without needing the message body at all. Deriving
state from the event log (and deliberately reusing `store.
ALLOWED_TRANSITIONS` / `store.EVENT_TYPES` -- the one place the state
machine is defined -- instead of re-encoding the transition table a
second time here) keeps `request-status` correct regardless of message-
body readability, rather than depending on it.

This is not, and was never accurately describable as, "dev-investigate
cannot read inbox message bodies" -- `inbox/<id>.json` is created by
`dev-investigate` itself (`store._atomic_create()` runs as the calling
process's EUID), at mode `0440`, which includes the owner-read bit; the
identity that wrote a file can always open it, independent of any ACL. An
earlier version of this file's docstring (and the implement record,
before review) claimed otherwise; see `docs/ai/reviews/
operator_request_channel/2026-08-08_005_implement_channel.md` for the
correction. The property `roles/operator_request_channel/defaults/
main.yml`'s ACL actually establishes is narrower and still correct:
`dev-investigate` cannot read content *another* identity wrote (Operator's
`outbox` entries, root-owned config/schema/ruleset) -- and since `inbox`
only ever receives messages `dev-investigate` itself submitted, there is
no cross-identity content in `inbox` for that property to protect in the
first place. `mark_expired_if_needed()`'s own docstring does not need this
distinction (it is only ever called with a message the caller already has
in hand), but `read_state_from_events()`'s reason for existing is a
best-practice choice (read only what you need; do not build a fresh code
path on an ownership detail the schema/ACL design did not set out to
guarantee), not an access limitation.
"""

import contextlib
import fcntl
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from . import ids, store

JST = timezone(timedelta(hours=9))

_TS_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

_EXPIRABLE_STATES = frozenset({"submitted", "accepted"})


class LifecycleError(Exception):
    """Fail-closed: caller must not proceed with a request this module
    rejected. Never carries payload content or a raw timestamp value that
    originated from untrusted input."""


def now_iso(now: Optional[datetime] = None) -> str:
    """Return `now` (or the current time) as a JST string matching
    request-schema-v1.json's `created_at`/`expires_at` pattern. Always a
    real conversion result (skills/ansible-implementation-style/SKILL.md
    "時刻はJST") -- never a UTC value with a pasted "+0900" label."""
    moment = now if now is not None else datetime.now(JST)
    return moment.astimezone(JST).strftime(_TS_FORMAT)


def _parse_iso(value: Any) -> datetime:
    if not isinstance(value, str):
        raise LifecycleError("timestamp is not a string")
    try:
        return datetime.strptime(value, _TS_FORMAT)
    except ValueError:
        raise LifecycleError("unparseable timestamp")


def compute_expires_at(raw_expires_at: Optional[str], received_at: str, max_ttl_days: int, default_ttl_days: int) -> str:
    """Return the `expires_at` string to store for a newly minted message.

    `received_at` is the entry point's own freshly generated `created_at`
    (already `now_iso()`'s output) -- this function does not read the
    clock itself, so a single call site's `created_at` and `expires_at`
    can never disagree about "now".

    Raises LifecycleError (fail closed, requirement §6.1) if the caller
    supplied `raw_expires_at` and it is unparseable, not after
    `received_at`, or beyond `received_at + max_ttl_days`. When
    `raw_expires_at` is None, returns `received_at + default_ttl_days`
    (plan §2.4).
    """
    received_dt = _parse_iso(received_at)
    max_dt = received_dt + timedelta(days=max_ttl_days)
    if raw_expires_at is None:
        return now_iso(received_dt + timedelta(days=default_ttl_days))
    requested_dt = _parse_iso(raw_expires_at)
    if requested_dt <= received_dt:
        raise LifecycleError("expires_at is not after created_at")
    if requested_dt > max_dt:
        raise LifecycleError("expires_at exceeds max TTL")
    return raw_expires_at


def is_expired(expires_at: Any, now: Optional[datetime] = None) -> bool:
    moment = now if now is not None else datetime.now(JST)
    return moment.astimezone(JST) > _parse_iso(expires_at)


@contextlib.contextmanager
def _events_file_lock(spool_dir: str, request_id: str):
    """Exclusive advisory lock (`flock`) on `request_id`'s own events
    file, held for the duration of the `with` block.

    Concurrency (review 2026-08-08_006 Suggestion 2): `store.
    append_event()` re-checks current state immediately before writing,
    but that check-then-act pair is itself unprotected (its own docstring
    says so) -- two callers acting on the *same* request_id at effectively
    the same instant can both pass their own check and both write, even
    though only the first write was actually legal. For most transitions
    this just produces a rejected second call (the loser's fresh re-check,
    now seeing the first write, correctly raises `InvalidTransition`
    *before* writing). But `ALLOWED_TRANSITIONS["expired"]` is empty, so a
    second "expired" line specifically is not a rejected-but-harmless
    collision: it lands, and it makes every future read of this request
    raise `StoreInconsistent` permanently -- reachable by ordinary
    concurrent reads alone (an ansy status poll and an Operator
    `list-pending` both racing the same request's expiry), not by an
    attacker or a broken client.

    Every entry-point call site that appends a *transition* event to an
    *already-existing* request_id (accept/reject/expired/answered) takes
    this lock first -- `mark_expired_if_needed()` and
    `append_event_locked()` below are the only two ways this module
    appends such an event, and both go through this same lock on the same
    file, so they correctly serialize against each other too. The very
    first "submitted" event on a freshly minted request_id does not need
    this (`write_accepted()`) -- nothing else can reference an id that was
    just generated by this same call.

    No `store.py` change was needed for this: the lock lives entirely in
    this file, on a file store.py already owns the layout of.
    """
    events_path = os.path.join(spool_dir, "events", request_id + ".jsonl")
    try:
        lock_fd = os.open(events_path, os.O_RDONLY)
    except OSError as exc:
        # The events file a caller's already-read state came from moments
        # ago should still be there; if it is not (or is not openable), do
        # not fall back to an unlocked append -- that would just
        # reintroduce the race this lock exists to close. Fail closed like
        # every other StoreError.
        raise store.StoreError("cannot open event log for locking: {}".format(type(exc).__name__))
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def append_event_locked(spool_dir: str, request_id: str, event_type: str, occurred_at: str, extra: Optional[Dict[str, Any]] = None) -> None:
    """`store.append_event()`, serialized against every other locked
    caller for the same request_id via `_events_file_lock()`. Entry points
    must use this (never call `store.append_event()` directly) whenever
    the event being appended is a transition on a request that already
    exists: `accept-request`, `reject-request`, and the "answered" append
    `_create_response()` makes on the OPREQ being replied to. See
    `_events_file_lock()`'s docstring for why.
    """
    with _events_file_lock(spool_dir, request_id):
        store.append_event(spool_dir, request_id, event_type, occurred_at, extra)


def mark_expired_if_needed(spool_dir: str, box: str, request_id: str, message: Dict[str, Any], state: str, now: Optional[datetime] = None) -> str:
    """Given an already-read `(message, state)` pair (from
    `store.read_message()`), append an `expired` event and return
    `"expired"` if the request's TTL has passed and it is still in an
    expirable state (`submitted` or `accepted`); otherwise return `state`
    unchanged.

    Precondition: caller already holds `message` (this never opens the
    message file itself). Callers that do not read the message file use
    `read_state_from_events()` instead and do not mark expiry. That is a
    design choice -- the status path has no need for the body -- not an
    access limitation: the submitting identity owns what it wrote to
    `inbox` and can read it through the owner bit regardless of the ACL
    (see plan 2026-08-08_002 §2.3).

    Concurrency: serialized via `_events_file_lock()` -- see that
    function's docstring for the full reasoning (review 2026-08-08_006
    Suggestion 2). Whichever caller gets the lock first re-reads state
    *under the lock* via `read_state_from_events()` (no `store.py` change
    needed -- this reuses the same event-log-only reader `oprc-receive`'s
    inbox-side `request-status` already relies on) and only then appends;
    the loser, once it acquires the lock, sees the already-updated state
    and returns without writing anything.
    """
    if state not in _EXPIRABLE_STATES:
        return state
    expires_at = message.get("expires_at")
    if not isinstance(expires_at, str):
        return state
    try:
        if not is_expired(expires_at, now):
            return state
    except LifecycleError:
        # A message that passed schema validation at creation time cannot
        # have an unparseable expires_at; treat defensively as "not
        # determinable" rather than silently marking it expired.
        return state

    with _events_file_lock(spool_dir, request_id):
        # Re-read under the lock: the `state` argument may already be
        # stale by the time we get here, including because another
        # process just finished marking this same request expired (or
        # accepted/rejected it -- either way, it is no longer expirable).
        current_state = read_state_from_events(spool_dir, request_id)
        if current_state not in _EXPIRABLE_STATES:
            return current_state
        store.append_event(spool_dir, request_id, "expired", now_iso(now))
        return "expired"


def read_state_from_events(spool_dir: str, request_id: str) -> str:
    """Determine current state from the event log alone -- no message-file
    read required (see module docstring for why `oprc-receive` needs
    this). Raises `store.StoreNotFound` if no event log exists,
    `store.StoreInconsistent` if it is malformed or contains an illegal
    transition -- the same exceptions `store.read_message()` raises, so
    callers can handle both uniformly.
    """
    path = os.path.join(spool_dir, "events", request_id + ".jsonl")
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        raise store.StoreNotFound(request_id)

    state: Optional[str] = None
    saw_any = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            raise store.StoreInconsistent("event line is not valid JSON")
        if not isinstance(record, dict) or record.get("request_id") != request_id:
            raise store.StoreInconsistent("event request_id mismatch")
        event_type = record.get("event")
        if event_type not in store.EVENT_TYPES:
            raise store.StoreInconsistent("unknown event type in event log")
        allowed = store.ALLOWED_TRANSITIONS.get(state, frozenset())
        if event_type not in allowed:
            raise store.StoreInconsistent("event log contains an illegal transition")
        state = event_type
        saw_any = True

    if not saw_any:
        raise store.StoreNotFound(request_id)
    return state


def load_verified_schema_and_ruleset(config_module, schema_module, cfg: Dict[str, Any]):
    """Shared "load schema doc + verify schema hash + load/verify DLP
    ruleset" sequence, used identically by oprc-receive and
    operator-channel before either accepts a new submission. Takes the
    `config` / `schema` modules as parameters rather than importing them
    here to avoid a circular import (config.py already imports dlp.py; a
    top-level `from . import config` here plus config.py importing this
    module back would cycle) -- entry points already import both modules
    for other calls, so passing them in costs nothing extra.

    Raises whatever `schema.SchemaError` / `config.ConfigError` the
    underlying calls raise; callers treat both as fail-closed.
    """
    schema_doc = schema_module.load_schema(cfg["schema_path"])
    config_module.verify_schema_hash(cfg)
    ruleset = config_module.load_and_verify_dlp_ruleset(cfg)
    return schema_doc, ruleset


def write_rejection(
    spool_dir: str,
    audit_log_path: str,
    source: str,
    stage: str,
    category: Optional[str] = None,
    rule_id: Optional[str] = None,
    pointer: Optional[str] = None,
    dlp_engine_version: Optional[str] = None,
    dlp_ruleset_sha256: Optional[str] = None,
    now: Optional[datetime] = None,
) -> str:
    """Record a pre-acceptance rejection (requirement §7.2, §15): no
    request id is minted for the rejected payload, no payload content or
    DLP-detected value is stored -- only the fixed, value-free fields §15
    lists for a rejected attempt. Returns the generated `attempt_id`
    (callers may echo it on stderr; it identifies the quarantine/audit
    record, not the payload).
    """
    attempt_id = ids.generate_attempt_id(now)
    occurred_at = now_iso(now)
    record: Dict[str, Any] = {
        "attempt_id": attempt_id,
        "occurred_at": occurred_at,
        "source": source,
        "stage": stage,
    }
    if category is not None:
        record["category"] = category
    if rule_id is not None:
        record["rule_id"] = rule_id
    if pointer is not None:
        record["pointer"] = pointer
    if dlp_engine_version is not None:
        record["dlp_engine_version"] = dlp_engine_version
    if dlp_ruleset_sha256 is not None:
        record["dlp_ruleset_sha256"] = dlp_ruleset_sha256
    store.write_quarantine(spool_dir, attempt_id, record)
    store.append_audit(audit_log_path, record)
    return attempt_id


def write_accepted(spool_dir: str, box: str, audit_log_path: str, request_id: str, message: Dict[str, Any], meta: Dict[str, Any]) -> None:
    """Persist a newly-validated, DLP-clean message: create the message
    file and append its `submitted` event and matching audit line
    (requirement §15's accepted-message field list) as one call, used
    identically by oprc-receive's `submit` and operator-channel's
    OPRES/DEVREQ creation. Capacity must already have been checked by the
    caller (`store.check_capacity`) -- this does not check it again.
    """
    created_at = message["created_at"]
    store.create_message(spool_dir, box, request_id, message, meta)
    store.append_event(spool_dir, request_id, "submitted", created_at)
    store.append_audit(
        audit_log_path,
        {
            "request_id": request_id,
            "conversation_id": message.get("conversation_id"),
            "type": message.get("type"),
            "source": message.get("source"),
            "created_at": created_at,
            "content_sha256": meta.get("content_sha256"),
            "schema_version": message.get("schema_version"),
            "dlp_engine_version": meta.get("dlp_engine_version"),
            "dlp_ruleset_sha256": meta.get("dlp_ruleset_sha256"),
            "event": "submitted",
            "result": "accepted",
        },
    )


def run_entrypoint(dispatch, argv) -> None:
    """The single shared exception safety net all three entry points
    (`bin/oprc-receive`, `bin/operator-channel`, `bin/operator-channel-client`)
    must use as their `main()`, instead of each defining its own
    `try/except` (2026-08-08 deploy verification item 2, then consolidated
    here per Operator review on quory: three independent copies is exactly
    the kind of thing that drifts, and the day one of them drifts is the
    day it starts leaking a traceback the other two don't).

    Contract (`dispatch(argv)` may raise anything; this function
    guarantees the following regardless of what it raises):

    - `PermissionError` and `OSError` are caught -- both are `Exception`
      subclasses, so the blanket `except Exception` below already covers
      them; named explicitly here because `PermissionError` is exactly
      the class the real-world bug that prompted this function was
      (`store.count_and_size()`'s `os.listdir()` against an ACL that did
      not yet grant directory-level read).
    - No traceback is ever printed.
    - The exception's own message (`str(exc)`) is never printed -- only
      `type(exc).__name__` (the class name), which cannot be derived from
      payload content, unlike an arbitrary exception message might be
      (an exception raised while processing a payload can and does
      sometimes embed a fragment of what it was processing -- a bad key,
      a truncated value -- in its own message; the class name never can).
    - No payload, path, or DLP-detected value is printed by this function
      -- it never touches any of those itself; it only ever receives the
      exception object `dispatch()` raised.
    - Output is exactly one line, `error: unexpected internal failure
      (<ExceptionClassName>)`, to stderr, and a non-zero exit -- fail
      closed for anything unanticipated, the same discipline every other
      failure path in these three files already follows for the failures
      it did anticipate.

    `SystemExit` (raised by every entry point's own `_deny()`/`_error()`
    calls) is deliberately not caught -- it is not an `Exception`
    subclass, so the normal `denied:`/`error:` exit paths those functions
    already implement are completely unaffected; this function only ever
    engages for something none of those paths anticipated.
    """
    try:
        dispatch(argv)
    except Exception as exc:  # noqa: BLE001 -- intentional catch-all, see docstring
        print("error: unexpected internal failure ({})".format(type(exc).__name__), file=sys.stderr)
        sys.exit(1)
