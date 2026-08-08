"""Canonical JSON serialization and content hashing (requirement §16, §7.1).

Both ansy and quory run this exact file (deployed via `copy`), so as long
as the input is a plain JSON-compatible structure (dict / list / str / int
/ float / bool / None) that has already passed through `wire.parse_payload`
(which rejects non-finite numbers and duplicate keys before this module
ever sees the data), `canonical_bytes()` produces byte-identical output on
both hosts for the same logical content.

This module does not re-validate its input for finiteness or duplicate
keys -- that is `wire.py`'s job, once, at the boundary. Doing it twice
would only create a second place that could disagree about what counts as
"finite" or "duplicate".
"""

import hashlib
import json
from typing import Any


def canonical_bytes(obj: Any) -> bytes:
    """Serialize `obj` into canonical JSON bytes.

    Canonical form: object keys sorted lexicographically, no insignificant
    whitespace, UTF-8 encoding with non-ASCII characters emitted literally
    (not \\uXXXX-escaped), so the same codepoint sequence always yields the
    same bytes regardless of which escaping a particular json encoder might
    otherwise choose. `allow_nan=False` makes this raise ValueError rather
    than silently emit non-JSON tokens (`NaN`, `Infinity`) if a caller ever
    hands in a value that should have been rejected earlier.
    """
    text = json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return text.encode("utf-8")


def content_hash(obj: Any) -> str:
    """Return the lowercase hex sha256 digest of `obj`'s canonical JSON."""
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def sha256_hex(data: bytes) -> str:
    """Plain sha256 hex digest of raw bytes (deployed files, ruleset bytes,
    etc.) -- not a canonical-JSON hash, just a straightforward byte hash
    used by config.py to compare a deployed file against an expected value.
    """
    return hashlib.sha256(data).hexdigest()
