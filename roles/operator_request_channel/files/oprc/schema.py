"""JSON Schema subset validator for the Operator Request Channel wire
schema, plus the small set of cross-field rules requirement §6.1/§6.2
define that a JSON Schema document cannot express on its own.

`request-schema-v1.json` is the single source of truth for field-level
constraints (required-ness, type, length, pattern, enum, item shape). This
module reads those constraints from the schema document at call time and
must never grow a second, hardcoded copy of any of them -- if a constraint
needs to change, it changes in the JSON file only.

Supported schema keywords are exactly the ones `request-schema-v1.json`
uses: `type` (a string or a list of strings, including "null"),
`properties`, `required`, `additionalProperties` (bool only), `enum`,
`const`, `pattern`, `minLength`, `maxLength`, `minItems`, `maxItems`,
`items` (a single schema applied to every array element), plus the
non-validating metadata keywords `$schema`, `$id`, `title`, `description`.
`load_schema()` refuses to load a document that uses anything else, so a
future schema author gets a clear failure instead of a silently-ignored
keyword.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

_SUPPORTED_KEYWORDS = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "enum",
    "const",
    "pattern",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "items",
    "description",
    "title",
    "$schema",
    "$id",
}


class SchemaError(Exception):
    """The schema document itself cannot be used (missing, unreadable,
    malformed, or uses an unsupported keyword). Fail closed: callers must
    not fall back to skipping validation."""


class ValidationError(Exception):
    """A payload does not conform to the schema, or violates one of the
    local (non-schema) relationship rules below.

    `errors` is a list of (json_pointer, rule) pairs. `rule` names the
    violated constraint (e.g. "required", "pattern", "maxLength") but never
    the offending value -- payload content can be attacker-controlled, and
    the same no-value-in-output discipline requirement §9.4 sets for DLP
    findings applies here too.
    """

    def __init__(self, errors: List[Tuple[str, str]]):
        self.errors = errors
        super().__init__("; ".join("{}: {}".format(p, r) for p, r in errors))


def load_schema(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as exc:
        raise SchemaError("cannot load schema: {}".format(type(exc).__name__))
    _check_supported(doc, "#")
    return doc


def _check_supported(node: Any, pointer: str) -> None:
    if not isinstance(node, dict):
        raise SchemaError("schema node at {} is not an object".format(pointer))
    unknown = set(node.keys()) - _SUPPORTED_KEYWORDS
    if unknown:
        raise SchemaError(
            "unsupported schema keyword(s) at {}: {}".format(pointer, sorted(unknown))
        )
    properties = node.get("properties")
    if isinstance(properties, dict):
        for name, subschema in properties.items():
            _check_supported(subschema, "{}/properties/{}".format(pointer, name))
    items = node.get("items")
    if isinstance(items, dict):
        _check_supported(items, pointer + "/items")


def _pointer_escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _type_matches(value: Any, type_spec: Any) -> bool:
    types = type_spec if isinstance(type_spec, list) else [type_spec]
    for t in types:
        if t == "object" and isinstance(value, dict):
            return True
        if t == "array" and isinstance(value, list):
            return True
        if t == "string" and isinstance(value, str):
            return True
        if t == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if t == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if t == "boolean" and isinstance(value, bool):
            return True
        if t == "null" and value is None:
            return True
    return False


def _validate_node(value: Any, node: Dict[str, Any], pointer: str, errors: List[Tuple[str, str]]) -> None:
    display_pointer = pointer or "/"

    if "const" in node:
        if value != node["const"]:
            errors.append((display_pointer, "const"))
            return
    if "enum" in node:
        if value not in node["enum"]:
            errors.append((display_pointer, "enum"))
            return
    if "type" in node:
        if not _type_matches(value, node["type"]):
            errors.append((display_pointer, "type"))
            return

    if isinstance(value, str):
        min_len = node.get("minLength")
        max_len = node.get("maxLength")
        if min_len is not None and len(value) < min_len:
            errors.append((display_pointer, "minLength"))
        if max_len is not None and len(value) > max_len:
            errors.append((display_pointer, "maxLength"))
        pattern = node.get("pattern")
        if pattern is not None and re.search(pattern, value) is None:
            errors.append((display_pointer, "pattern"))

    if isinstance(value, list):
        min_items = node.get("minItems")
        max_items = node.get("maxItems")
        if min_items is not None and len(value) < min_items:
            errors.append((display_pointer, "minItems"))
        if max_items is not None and len(value) > max_items:
            errors.append((display_pointer, "maxItems"))
        item_schema = node.get("items")
        if item_schema is not None:
            for idx, item in enumerate(value):
                _validate_node(item, item_schema, pointer + "/" + str(idx), errors)

    if isinstance(value, dict):
        properties = node.get("properties", {})
        required = node.get("required", [])
        for key in required:
            if key not in value:
                errors.append((pointer + "/" + _pointer_escape(key), "required"))
        if node.get("additionalProperties") is False:
            for key in value.keys():
                if key not in properties:
                    errors.append((pointer + "/" + _pointer_escape(key), "additionalProperties"))
        for key, subschema in properties.items():
            if key in value:
                _validate_node(value[key], subschema, pointer + "/" + _pointer_escape(key), errors)


def validate(payload: Any, schema: Dict[str, Any]) -> None:
    """Validate `payload` against `schema`. Raises ValidationError listing
    every violation found (not just the first); returns None on success."""
    errors: List[Tuple[str, str]] = []
    _validate_node(payload, schema, "", errors)
    if errors:
        raise ValidationError(errors)


# --- requirement §6.1: fields the receiving side assigns, never the client ---

SERVER_ASSIGNED_FIELDS = ("request_id", "source", "created_at")


def reject_server_assigned_fields(raw_payload: Dict[str, Any]) -> None:
    """Raise ValidationError if a raw client submission already sets any of
    `request_id` / `source` / `created_at`.

    This must run on the payload as parsed from the wire, *before* the
    receiving side fills those fields in -- once they exist, the schema is
    supposed to require them (a complete stored message has them), which is
    the opposite constraint. Deliberately not a schema keyword: JSON Schema
    has no "must NOT be present yet" concept that also flips to "must be
    present later" for the same field, and encoding half of that in the
    schema and half here would be exactly the kind of drift this module's
    docstring says to avoid. So this rule lives entirely in code, and
    encodes no field-level constraint (length/pattern/type) that the schema
    already owns -- it only checks key presence.
    """
    if not isinstance(raw_payload, dict):
        raise ValidationError([("/", "type")])
    present = [f for f in SERVER_ASSIGNED_FIELDS if f in raw_payload]
    if present:
        raise ValidationError([("/" + f, "server_assigned_field_in_payload") for f in present])


# --- requirement §4.2: identity -> allowed message type ---

SOURCE_ALLOWED_TYPES = {
    "coordinator": frozenset({"OPREQ"}),
    "operator": frozenset({"OPRES", "DEVREQ"}),
}


def validate_source_type_allowed(source: str, type_: str) -> None:
    allowed = SOURCE_ALLOWED_TYPES.get(source)
    if not allowed or type_ not in allowed:
        raise ValidationError([("/source", "source_type_not_allowed")])


# --- requirement §6.2: relationship rules that need no store lookup ---


def validate_local_relationships(message: Dict[str, Any]) -> None:
    """Local-only §6.2 checks, i.e. ones decidable from `message` alone:

    - a new OPREQ always starts its own conversation: `in_reply_to` must be
      empty/null.

    Checks that need *another* message (does the referenced request exist,
    is the type combination allowed, does the conversation match) require a
    store lookup and are `validate_reply_target()`'s job below -- the
    caller fetches the referenced message via store.py first.
    """
    if message.get("type") == "OPREQ" and message.get("in_reply_to"):
        raise ValidationError([("/in_reply_to", "opreq_must_not_reply")])


# requirement §6.2 "OPRESは応答対象のOPREQを in_reply_to で参照" / "OPREQへの応答
# として作るDEVREQ" -- a reply's allowed target type, keyed by the replying
# message's own type.
REPLY_ALLOWED_TARGET_TYPES = {
    "OPRES": frozenset({"OPREQ"}),
    "DEVREQ": frozenset({"OPREQ"}),
}


def validate_reply_target(message: Dict[str, Any], referenced_message: Dict[str, Any]) -> None:
    """Given a message with a non-empty `in_reply_to` and the message it
    points at (already fetched by the caller -- this function does no
    I/O), check: the referenced type is one this type is allowed to reply
    to, and `conversation_id` matches.

    Precondition: `message["in_reply_to"] == referenced_message["request_id"]`;
    the caller is responsible for that lookup succeeding (a lookup miss is
    "存在しないrequestへの参照" and is the caller's own StoreNotFound path,
    not something this function can detect).
    """
    type_ = message.get("type")
    allowed_targets = REPLY_ALLOWED_TARGET_TYPES.get(type_)
    if not allowed_targets or referenced_message.get("type") not in allowed_targets:
        raise ValidationError([("/in_reply_to", "reply_type_not_allowed")])
    if message.get("conversation_id") != referenced_message.get("conversation_id"):
        raise ValidationError([("/conversation_id", "conversation_mismatch")])
