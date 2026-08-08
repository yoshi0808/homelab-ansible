"""Config loading and the fail-closed gates that must pass before any
DLP-guarded operation proceeds (requirement §9.2): engine-version /
ruleset-hash / schema-hash verification, and (quory-only, plan §2.11) time
synchronization for the two entry points that mint `created_at`.

Both are read-only checks against local files and a local command; neither
touches the spool. `store.py` is what turns "config says we may proceed"
into an actual write.
"""

import json
import re
import subprocess
from typing import Any, Dict

from . import canonical, dlp

CHRONYC_PATH = "/usr/bin/chronyc"


class ConfigError(Exception):
    """Config missing, unreadable, malformed, or failing a required check.
    Every raise site in this module is a fail-closed point: callers must
    treat any ConfigError as "do not proceed", never retry with a relaxed
    check."""


class TimeSyncError(Exception):
    """Time synchronization could not be confirmed (plan §2.11). Used only
    to gate operations that mint a new `created_at` / request_id /
    conversation_id (submit, and Operator-created OPRES/DEVREQ) -- get /
    list / status must not call `assert_time_synced()`.

    Never carries the actual clock offset or raw chronyc output in its
    message: an offset is not a secret, but this module holds to the same
    no-value-in-output discipline as DLP anyway, so a caller can log a
    ConfigError/TimeSyncError message verbatim without a second review
    pass to check what's inside it.
    """


REQUIRED_COMMON_KEYS = (
    "config_version",
    "role",
    "channel_enabled",
    "libexec_dir",
    "schema_path",
    "dlp_rules_path",
    "expected_schema_sha256",
    "expected_dlp_engine_version",
    "expected_dlp_ruleset_sha256",
    "max_payload_bytes",
    "dlp_timeout_seconds",
)

REQUIRED_COORDINATOR_KEYS = ("ssh_destination", "ssh_connect_timeout_seconds")

REQUIRED_OPERATOR_HOST_KEYS = (
    "spool_dir",
    "audit_log_path",
    "max_ttl_days",
    "default_ttl_days",
    "max_messages_per_box",
    "max_total_bytes",
    "page_size",
)


def load_config(path: str) -> Dict[str, Any]:
    """Load and structurally validate config.json for this host's role.

    `role` must be "coordinator" (ansy) or "operator_host" (quory); the
    corresponding extra required keys are checked in addition to the
    common set. Raises ConfigError on any problem -- missing file,
    malformed JSON, non-object root, missing required key, or unknown
    role.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as exc:
        raise ConfigError("cannot load config: {}".format(type(exc).__name__))
    if not isinstance(doc, dict):
        raise ConfigError("config root must be an object")

    missing = [k for k in REQUIRED_COMMON_KEYS if k not in doc]
    role = doc.get("role")
    if role == "coordinator":
        missing += [k for k in REQUIRED_COORDINATOR_KEYS if k not in doc]
    elif role == "operator_host":
        missing += [k for k in REQUIRED_OPERATOR_HOST_KEYS if k not in doc]
    else:
        raise ConfigError("unknown or missing role: {!r}".format(role))
    if missing:
        raise ConfigError("config missing required key(s): {}".format(", ".join(sorted(missing))))
    return doc


def verify_schema_hash(config: Dict[str, Any]) -> None:
    """Raise ConfigError unless the file at config["schema_path"] hashes to
    config["expected_schema_sha256"]. Requirement §9.2: "engine version
    または ruleset hash が期待値と一致しない" is fail-closed; the schema hash
    is the same discipline applied to the schema file."""
    path = config["schema_path"]
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as exc:
        raise ConfigError("cannot read schema file: {}".format(type(exc).__name__))
    if canonical.sha256_hex(data) != config["expected_schema_sha256"]:
        raise ConfigError("schema hash mismatch")


def load_and_verify_dlp_ruleset(config: Dict[str, Any]) -> Dict[str, Any]:
    """Load dlp-rules.json, verify its file hash and engine_version both
    match the config's expected values, and return the parsed+compiled
    ruleset ready for `dlp.scan()`.

    Raises ConfigError on any mismatch or load failure -- callers must not
    fall back to an unverified ruleset.
    """
    path = config["dlp_rules_path"]
    try:
        with open(path, "rb") as f:
            raw_bytes = f.read()
    except OSError as exc:
        raise ConfigError("cannot read dlp ruleset file: {}".format(type(exc).__name__))

    if canonical.sha256_hex(raw_bytes) != config["expected_dlp_ruleset_sha256"]:
        raise ConfigError("dlp ruleset hash mismatch")
    if config["expected_dlp_engine_version"] != dlp.ENGINE_VERSION:
        raise ConfigError("dlp engine_version mismatch")

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise ConfigError("dlp ruleset is not valid utf-8")
    try:
        ruleset = dlp.parse_ruleset(text)
    except dlp.RulesetError as exc:
        raise ConfigError("dlp ruleset invalid: {}".format(exc))
    if ruleset["engine_version"] != config["expected_dlp_engine_version"]:
        raise ConfigError("dlp ruleset engine_version mismatch")
    return ruleset


# --- plan §2.11: new-submission time-sync gate (quory only) ---

_LEAP_STATUS_RE = re.compile(r"^Leap status\s*:", re.MULTILINE)
_NOT_SYNCHRONISED_TEXT = "Not synchronised"
_SYSTEM_TIME_OFFSET_RE = re.compile(
    r"^System time\s*:\s*([0-9]+(?:\.[0-9]+)?)\s+seconds\s+(?:slow|fast)",
    re.MULTILINE,
)


def assert_time_synced(
    max_offset_seconds: float = 60.0,
    timeout_seconds: float = 5.0,
    chronyc_path: str = CHRONYC_PATH,
) -> None:
    """Raise TimeSyncError unless `chronyc tracking` reports a synchronized,
    in-bounds clock (plan §2.11's five fail-closed conditions: non-zero
    exit, no `Leap status` line, `Not synchronised` present, unparseable
    `System time` offset, or offset beyond `max_offset_seconds` -- each of
    these raises rather than being treated as "probably fine").

    Fixed argv (no shell), stdin closed, bounded timeout. Call this only
    from the two entry points that mint a new `created_at` (submit,
    Operator-created OPRES/DEVREQ) -- get/list/status must keep working
    even when this would fail (requirement §16 "channelの障害が既存
    read-only調査を停止させない", applied the same way inside this
    channel's own operations).
    """
    try:
        proc = subprocess.run(
            [chronyc_path, "tracking"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise TimeSyncError("chronyc unavailable or timed out")

    if proc.returncode != 0:
        raise TimeSyncError("chronyc exited non-zero")

    try:
        output = proc.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise TimeSyncError("chronyc output not utf-8")

    if not _LEAP_STATUS_RE.search(output):
        raise TimeSyncError("no Leap status line")
    if _NOT_SYNCHRONISED_TEXT in output:
        raise TimeSyncError("not synchronised")

    match = _SYSTEM_TIME_OFFSET_RE.search(output)
    if not match:
        raise TimeSyncError("cannot parse System time offset")
    offset = float(match.group(1))
    if offset > max_offset_seconds:
        raise TimeSyncError("clock offset exceeds threshold")
