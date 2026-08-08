"""Raw payload parsing: bytes -> dict.

Enforces the wire-level invariants that apply uniformly to every message
type, before any schema field is even looked at (requirement §6.3, §16):
size bound, UTF-8 validity, well-formed Unicode, no duplicate JSON object
keys, no non-finite numbers, bounded nesting depth.

None of this duplicates a constraint that `request-schema-v1.json` owns --
the schema says nothing about byte size, key duplication, or nesting depth
(those are not JSON Schema concepts), so there is nothing here for
`schema.py` to disagree with. This module rejects a payload before it is
structured enough to validate against a schema at all.
"""

import json
from typing import Any, Dict

# Generous relative to the actual message shape (which nests at most 3-4
# levels: object -> array -> object -> string, e.g. evidence_references).
# This exists to bound recursion/resource use on adversarial input, not to
# describe the schema's real shape -- see schema.py for that.
MAX_DEPTH = 8


class WireError(Exception):
    """Any WireError means: stop, do not attempt to interpret this payload
    further. `reason` is a short fixed code and must never be built from
    payload content (requirement §9.4's no-value-in-output discipline
    applies here too, even though this module runs before DLP)."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _no_duplicate_keys(pairs):
    seen = set()
    out = {}
    for key, value in pairs:
        if key in seen:
            raise WireError("duplicate_key")
        seen.add(key)
        out[key] = value
    return out


def _reject_constant(name: str):
    # json.loads calls this for the literals NaN / Infinity / -Infinity.
    raise WireError("non_finite_number")


def _check_structure(value: Any, depth: int) -> None:
    """Recursively enforce the depth bound and reject any string leaf that
    contains a lone surrogate. A lone surrogate cannot appear from raw
    UTF-8 bytes (strict decode already rejects that) but *can* appear
    after JSON unescapes a `\\uD800`-`\\uDFFF` escape sequence that was
    never paired -- so this check has to run on the parsed value, not the
    raw wire text.
    """
    if depth > MAX_DEPTH:
        raise WireError("nesting_too_deep")
    if isinstance(value, str):
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
            raise WireError("invalid_unicode")
    elif isinstance(value, dict):
        for sub in value.values():
            _check_structure(sub, depth + 1)
    elif isinstance(value, list):
        for sub in value:
            _check_structure(sub, depth + 1)


def parse_payload(raw: bytes, max_bytes: int) -> Dict[str, Any]:
    """Parse `raw` into a dict, or raise WireError.

    Preconditions: `raw` is bytes/bytearray, `max_bytes` > 0.
    Postcondition on success: the return value is a `dict` whose only
    JSON-native types are str / int / float / bool / None / dict / list,
    with no duplicate keys anywhere and no non-finite numbers anywhere.
    Field-level shape (required keys, patterns, lengths) is NOT checked
    here -- that is schema.validate()'s job.
    """
    if not isinstance(raw, (bytes, bytearray)):
        raise TypeError("raw must be bytes")
    if len(raw) == 0:
        raise WireError("empty_payload")
    if len(raw) > max_bytes:
        raise WireError("payload_too_large")

    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise WireError("invalid_utf8")

    try:
        obj = json.loads(
            text,
            object_pairs_hook=_no_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except ValueError:
        raise WireError("invalid_json")

    if not isinstance(obj, dict):
        raise WireError("not_an_object")

    # Lone surrogates smuggled in via \uD800-\uDFFF JSON escapes decode
    # "successfully" into Python str values (surrogate code points are
    # legal within a Python str) but are not valid Unicode text. This can
    # only be caught after json.loads() has unescaped them -- the raw wire
    # bytes never contain the surrogate itself, only the six-character
    # escape sequence -- so the check runs here, walking the parsed
    # structure, and is combined with the depth bound for a single pass.
    _check_structure(obj, 1)
    return obj
