"""The single DLP engine, driven entirely by `dlp-rules.json`.

Used identically at all four inspection points (requirement §9.1): ansy
submit, quory accept, quory outbound, ansy pull. Every caller loads the
same ruleset file (deployed byte-identical via `copy`, hash-checked by
`config.py`) and calls `scan()` with it; this module holds no
channel-specific field names or category patterns of its own, so there is
exactly one place the detection logic can drift out of sync with itself.

Fail-closed discipline (requirement §9.2, §9.4): `scan()` either returns a
`ScanResult` or raises. It never returns a partial result, and neither the
return value, `Finding` objects, nor any exception message this module
raises ever contain the string that matched -- only category, rule id, and
JSON Pointer location. Callers must keep that discipline too: do not log
`payload` alongside a `ScanResult`.
"""

import json
import math
import re
import signal
from typing import Any, Dict, List, Optional

ENGINE_VERSION = "1"


class DlpError(Exception):
    """Base class; any DlpError means "do not proceed" for the caller."""


class RulesetError(DlpError):
    """Ruleset file missing, unreadable, malformed, or using an engine
    version this code does not implement."""


class ScanTimeout(DlpError):
    """Scan did not complete within the configured timeout, or this
    process/thread cannot support the timeout mechanism at all -- either
    way, requirement §9.2 says fail closed, not "scan without a bound"."""


class Finding:
    __slots__ = ("category", "rule_id", "pointer")

    def __init__(self, category: str, rule_id: str, pointer: str):
        self.category = category
        self.rule_id = rule_id
        self.pointer = pointer

    def to_dict(self) -> Dict[str, str]:
        return {"category": self.category, "rule_id": self.rule_id, "pointer": self.pointer}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return "Finding(category={!r}, rule_id={!r}, pointer={!r})".format(
            self.category, self.rule_id, self.pointer
        )


class ScanResult:
    def __init__(self, findings: List[Finding]):
        self.findings = findings

    @property
    def blocked(self) -> bool:
        return len(self.findings) > 0


_REQUIRED_RULE_KEYS = {"id", "category", "pattern"}


def load_ruleset(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as exc:
        raise RulesetError("cannot read ruleset: {}".format(type(exc).__name__))
    return parse_ruleset(raw)


def parse_ruleset(raw_text: str) -> Dict[str, Any]:
    """Parse and compile a ruleset document. Raises RulesetError on any
    structural problem -- callers must treat that as fail-closed, not as
    "run with an empty ruleset"."""
    try:
        doc = json.loads(raw_text)
    except ValueError as exc:
        raise RulesetError("ruleset is not valid JSON: {}".format(type(exc).__name__))
    if not isinstance(doc, dict):
        raise RulesetError("ruleset root must be an object")
    if doc.get("engine_version") != ENGINE_VERSION:
        raise RulesetError("ruleset engine_version does not match this engine")

    rules_raw = doc.get("rules")
    if not isinstance(rules_raw, list) or not rules_raw:
        raise RulesetError("ruleset has no rules")

    compiled_rules = []
    seen_ids = set()
    for rule in rules_raw:
        if not isinstance(rule, dict) or not _REQUIRED_RULE_KEYS.issubset(rule.keys()):
            raise RulesetError("malformed rule entry")
        rule_id = rule["id"]
        if rule_id in seen_ids:
            raise RulesetError("duplicate rule id: {}".format(rule_id))
        seen_ids.add(rule_id)
        try:
            pattern = re.compile(rule["pattern"], re.MULTILINE)
        except re.error:
            raise RulesetError("invalid regex in rule {}".format(rule_id))
        compiled_rules.append({"id": rule_id, "category": rule["category"], "pattern": pattern})

    compiled_entropy: Optional[Dict[str, Any]] = None
    entropy_raw = doc.get("entropy")
    if entropy_raw is not None:
        if not isinstance(entropy_raw, dict):
            raise RulesetError("entropy section must be an object")
        try:
            candidate_pattern = re.compile(entropy_raw["candidate_pattern"])
        except KeyError:
            raise RulesetError("entropy section missing candidate_pattern")
        except re.error:
            raise RulesetError("invalid entropy.candidate_pattern")
        scan_pointers = entropy_raw.get("scan_field_pointers")
        if not isinstance(scan_pointers, list) or not all(isinstance(p, str) for p in scan_pointers):
            raise RulesetError("entropy.scan_field_pointers must be a list of strings")
        compiled_entropy = {
            "id": entropy_raw.get("id", "high-entropy-string"),
            "category": entropy_raw.get("category", "high_entropy"),
            "min_length": int(entropy_raw.get("min_length", 20)),
            "min_bits_per_char": float(entropy_raw.get("min_bits_per_char", 3.8)),
            "candidate_pattern": candidate_pattern,
            "scan_field_pointers": scan_pointers,
        }

    return {
        "engine_version": doc["engine_version"],
        "ruleset_version": doc.get("ruleset_version", ""),
        "rules": compiled_rules,
        "entropy": compiled_entropy,
    }


def _pointer_escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _walk_strings(value: Any, pointer: str):
    if isinstance(value, str):
        yield (pointer or "/"), value
    elif isinstance(value, dict):
        for key, sub in value.items():
            for item in _walk_strings(sub, pointer + "/" + _pointer_escape(str(key))):
                yield item
    elif isinstance(value, list):
        for idx, sub in enumerate(value):
            for item in _walk_strings(sub, pointer + "/" + str(idx)):
                yield item


def _pointer_matches(pointer: str, patterns: List[str]) -> bool:
    """`patterns` entries may end with "/*" meaning "this field and
    everything nested under it"; anything else must match exactly. This is
    a small purpose-built matcher, not a general glob engine -- it exists
    only to let the ruleset say "scan inside this array" without the
    engine needing to know the array's name."""
    for p in patterns:
        if p.endswith("/*"):
            prefix = p[:-2]
            if pointer == prefix or pointer.startswith(prefix + "/"):
                return True
        elif pointer == p:
            return True
    return False


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts: Dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    length = len(s)
    total = 0.0
    for c in counts.values():
        p = c / length
        total -= p * math.log2(p)
    return total


class _AlarmGuard:
    """Wall-clock timeout for the scan loop via SIGALRM.

    Unix + main-thread only. Both ansy and quory are Linux hosts, and every
    entry point that calls `scan()` is expected to be a short-lived,
    single-threaded CLI process (plan §2.1: "3つのエントリポイントはいずれも
    薄く"), so that is within this deployment's actual constraints. If a
    future caller ever violates that (calls from a non-main thread, or runs
    on a platform without SIGALRM), this fails closed with ScanTimeout
    rather than silently scanning without a bound.
    """

    def __init__(self, timeout_seconds: float):
        self._timeout = timeout_seconds
        self._old_handler = None

    def __enter__(self) -> "_AlarmGuard":
        if not hasattr(signal, "SIGALRM") or not hasattr(signal, "setitimer"):
            raise ScanTimeout("no interval-timer support on this platform")

        def _handler(signum, frame):
            raise ScanTimeout("dlp scan exceeded {}s".format(self._timeout))

        try:
            self._old_handler = signal.signal(signal.SIGALRM, _handler)
        except ValueError:
            raise ScanTimeout("dlp scan must run on the main thread")
        signal.setitimer(signal.ITIMER_REAL, self._timeout)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if self._old_handler is not None:
            signal.signal(signal.SIGALRM, self._old_handler)
        return False


def scan(payload: Dict[str, Any], ruleset: Dict[str, Any], timeout_seconds: float) -> ScanResult:
    """Scan every string value in `payload` against `ruleset`.

    Preconditions: `payload` is a JSON-compatible structure (as produced by
    `wire.parse_payload`); `ruleset` was produced by `parse_ruleset()` /
    `load_ruleset()` (not a hand-built dict -- the compiled `re.Pattern`
    objects are what makes this fast and correct).

    Returns a ScanResult (possibly with zero findings) or raises
    `ScanTimeout` if the scan did not finish in time. Never raises for
    "findings exist" -- that is a normal, successful scan; the caller
    decides what to do with `result.blocked`.
    """
    with _AlarmGuard(timeout_seconds):
        return _scan_impl(payload, ruleset)


def _scan_impl(payload: Any, ruleset: Dict[str, Any]) -> ScanResult:
    findings: List[Finding] = []
    strings = list(_walk_strings(payload, ""))

    for pointer, value in strings:
        for rule in ruleset["rules"]:
            if rule["pattern"].search(value):
                findings.append(Finding(rule["category"], rule["id"], pointer))

    entropy_cfg = ruleset.get("entropy")
    if entropy_cfg is not None:
        scan_pointers = entropy_cfg["scan_field_pointers"]
        for pointer, value in strings:
            if not _pointer_matches(pointer, scan_pointers):
                continue
            for match in entropy_cfg["candidate_pattern"].finditer(value):
                candidate = match.group(0)
                if len(candidate) < entropy_cfg["min_length"]:
                    continue
                if _shannon_entropy(candidate) >= entropy_cfg["min_bits_per_char"]:
                    findings.append(Finding(entropy_cfg["category"], entropy_cfg["id"], pointer))
                    break  # one finding per field is enough signal to reject

    return ScanResult(findings)
