"""request_id / conversation_id / attempt_id generation and validation
(plan §2.5).

Formats:

    req-YYYYMMDDTHHMMSS+0900-<hex16>   request_id
    cnv-YYYYMMDDTHHMMSS+0900-<hex16>   conversation_id
    att-YYYYMMDDTHHMMSS+0900-<hex16>   attempt_id (quarantine records only;
                                        not specified by requirement/plan,
                                        filled in here for symmetry -- see
                                        the implement record's assumptions)

The timestamp segment is a real conversion result, not a pasted label (see
skills/ansible-implementation-style/SKILL.md "時刻はJST"): it always comes
from `datetime.now(JST).strftime(...)`, never from string concatenation
with a hardcoded "+0900" applied to a differently-zoned value.

`.` and `/` are structurally unspellable in any of these three formats, so
path-traversal is not something a valid id can encode (same design as the
dispatcher's own FILE_RE, see roles/dev_investigate/files/
recovery-investigate-dispatch-quory.sh). Generation re-checks its own
output against the regex before returning it and fails closed
(`IdGenerationError`) if that ever disagrees -- that would be a bug in this
module, not bad input, and it must not hand back an id it cannot itself
parse back.
"""

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

JST = timezone(timedelta(hours=9))

_TS_RE = r"[0-9]{8}T[0-9]{6}\+0900"
_HEX_RE = r"[0-9a-f]{16}"

REQUEST_ID_RE = re.compile(r"^req-" + _TS_RE + r"-" + _HEX_RE + r"$")
CONVERSATION_ID_RE = re.compile(r"^cnv-" + _TS_RE + r"-" + _HEX_RE + r"$")
ATTEMPT_ID_RE = re.compile(r"^att-" + _TS_RE + r"-" + _HEX_RE + r"$")


class IdGenerationError(Exception):
    """Raised if a freshly generated id fails its own format check."""


def _new_id(prefix: str, pattern: "re.Pattern", now: Optional[datetime] = None) -> str:
    moment = now if now is not None else datetime.now(JST)
    ts = moment.astimezone(JST).strftime("%Y%m%dT%H%M%S%z")
    candidate = "{}-{}-{}".format(prefix, ts, secrets.token_hex(8))
    if not pattern.match(candidate):
        raise IdGenerationError("generated id failed its own format check: {}".format(prefix))
    return candidate


def generate_request_id(now: Optional[datetime] = None) -> str:
    return _new_id("req", REQUEST_ID_RE, now)


def generate_conversation_id(now: Optional[datetime] = None) -> str:
    return _new_id("cnv", CONVERSATION_ID_RE, now)


def generate_attempt_id(now: Optional[datetime] = None) -> str:
    return _new_id("att", ATTEMPT_ID_RE, now)


def is_valid_request_id(value: object) -> bool:
    return isinstance(value, str) and bool(REQUEST_ID_RE.match(value))


def is_valid_conversation_id(value: object) -> bool:
    return isinstance(value, str) and bool(CONVERSATION_ID_RE.match(value))


def is_valid_attempt_id(value: object) -> bool:
    return isinstance(value, str) and bool(ATTEMPT_ID_RE.match(value))
