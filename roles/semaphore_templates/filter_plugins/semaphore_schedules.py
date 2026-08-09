"""Semaphore schedules as code: preflight, diff, and payload logic for
roles/semaphore_templates schedule reconciliation.

Pure Python, no Ansible-only APIs and no network -- same discipline as the
sibling module `semaphore_templates.py` in this same filter_plugins
directory, and for the same reason (docs/ai/roles/implementer.md forbids
this Role from touching a real host at all, including read-only checks;
that is Tester's role). Everything here can be exercised with plain
python3 against fixture data; see scripts/tests/semaphore_schedules/.

Requirement (all IDs referenced in docstrings/comments below): docs/ai/
reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md.
Implement record for this pass: docs/ai/reviews/semaphore_schedules_as_
code/2026-08-09_015_implement_filters.md.

Scope boundary: this module owns the 8 functions in the requirement's
"確定済みインターフェース契約" table, plus `semaphore_schedules_
nonmanaged_diff` (added 2026-08-09 per independent review High #2 --
`verify` alone never checked non-managed fields, see that function's
docstring). It does not call the Semaphore API, does not decide whether
to write, and does not know about `--check` / `ansible_check_mode` -- all
of that lives in the task side (a separate, later Implementer pass).
Every function here is deterministic and total for well-typed input:
given the same arguments it always returns the same value, and it never
raises for data shapes this module cannot avoid receiving from a real API
response (task_params content this module does not recognize as safe is
reported as a *finding*, not an exception -- see
`_task_params_public_problems`, an allowlist, not a denylist -- rewritten
2026-08-09 per independent review High #3).
"""
from __future__ import annotations

import collections.abc
import json
import re
from urllib.parse import urlsplit, urlunsplit

# ---------------------------------------------------------------------------
# R8-2: the 5 managed fields as they appear on the API side (schedule GET/
# PUT/POST objects), in a fixed order used everywhere a field-name list is
# reported. Note this is *not* the same 5 names as R1's catalog fields --
# R1's `template` (a name) becomes `template_id` (a resolved id, R3) and
# R1's `cron` becomes `cron_format` (the API's own field name).
# ---------------------------------------------------------------------------
_MANAGED_FIELD_ORDER = ('name', 'cron_format', 'template_id', 'task_params', 'active')

# R8-3's first stage writes these 4 unconditionally, plus a stage-specific
# `active` (see semaphore_schedules_desired). The stage-2 precheck (R8-3)
# re-checks exactly these 4 plus an explicit `active is False` check.
_STAGE1_FIELD_ORDER = ('name', 'cron_format', 'template_id', 'task_params')

_REQUIRED_CATALOG_FIELDS = ('name', 'template', 'cron', 'active', 'task_params')


def _numeric_kind(value):
    """Classify `value` for _strict_equal's numeric guard, by what it
    *is* (via isinstance, so a real subclass -- Ansible-internal wrapper
    types included -- still classifies correctly) rather than by its
    exact class. `bool` is checked first because `bool` is itself an
    `int` subclass in Python. Returns 'bool' / 'int' / 'float' / None.
    """
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int):
        return 'int'
    if isinstance(value, float):
        return 'float'
    return None


def _strict_equal(a, b):
    """Value equality that does not fall through Python's numeric
    coercion (`1 == True` and `1 == 1.0` are both true under plain `==`),
    while *not* rejecting two values that are the same value wrapped in
    different-but-equivalent classes.

    R16-2 requires that a normalized or silently-retyped value on the API
    side (e.g. `active` coming back as `1` instead of `true`) be detected
    as a mismatch -- bare `!=` would miss exactly that case, since `bool`
    is a subclass of `int`. This module's first version over-corrected by
    requiring `type(a) is type(b)` for *everything*, which broke on real
    ansible-core input: Coordinator's 2026-08-09 measurement against
    ansible-core 2.20.1 found catalog values (from YAML) come back as
    `_AnsibleTaggedStr` / `_AnsibleLazyTemplateDict` while values that
    went through `from_json` (simulating an API response) are plain `str`
    / `dict` -- same value, same meaning, different class, and `type(a)
    is type(b)` treated every one of them as a mismatch even though
    Python's own `==` already correctly said they were equal.

    So: the type check only fires for the one case it exists to catch --
    numbers, where `bool`/`int`/`float` must agree on *kind* (via
    `_numeric_kind`, itself isinstance-based so a numeric wrapper
    subclass still classifies correctly). Every other type (str, dict,
    list, None, ...) is compared with plain `==` -- including recursively
    into `Mapping`/list-like containers, so a single retyped-but-still-
    numeric leaf inside `task_params` is still caught, and a mapping- or
    string-alike wrapper class at any depth is not.
    """
    a_kind = _numeric_kind(a)
    b_kind = _numeric_kind(b)
    if a_kind is not None or b_kind is not None:
        return a_kind == b_kind and a == b
    if isinstance(a, collections.abc.Mapping) and isinstance(b, collections.abc.Mapping):
        return set(a.keys()) == set(b.keys()) and all(
            _strict_equal(a[k], b[k]) for k in a
        )
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_strict_equal(x, y) for x, y in zip(a, b))
    return a == b


def _management_fields_from_raw(raw):
    """Project a raw schedule object (single-GET shape, R8) down to the 5
    managed fields, in the fixed order used for comparison everywhere.
    Deliberately does not distinguish "missing" from "explicitly None" --
    a raw object from a real GET always has all 5 keys; a `{}` passed in
    by a caller that has no detail yet (e.g. a not-yet-fetched schedule)
    projects to all-None, which compares unequal to any real desired state
    and is therefore treated as "needs a write", never silently skipped.
    """
    return {field: raw.get(field) for field in _MANAGED_FIELD_ORDER}


# ---------------------------------------------------------------------------
# R9 (4): cron validity.
#
# The exact grammar this Semaphore version (2.18.4) accepts has not been
# measured empirically -- reaching the API is Tester's role, not
# Implementer's (docs/ai/roles/implementer.md). This accepts the
# conservative, well-known 5-field POSIX-style grammar (`*`, `N`, `N-M`,
# comma lists of those, and an optional `/step` on any of them) with
# per-field value ranges, and rejects anything it cannot positively
# classify -- R9's "判定できないものは error 側へ倒す" applies here too.
# All 19 real cron strings quoted in the requirement (2026-08-09) are
# exercised as valid fixtures in the unit tests; grammar reconfirmation
# against the live API is explicitly deferred to test_plan (requirement
# §9).
# ---------------------------------------------------------------------------
_CRON_FIELD_BOUNDS = (
    (0, 59),  # minute
    (0, 23),  # hour
    (1, 31),  # day of month
    (1, 12),  # month
    (0, 7),   # day of week (0 and 7 both mean Sunday)
)

_CRON_TOKEN_RE = re.compile(r'^(\*|[0-9]+)(-[0-9]+)?(/[0-9]+)?$')


def _cron_field_is_valid(field, bounds):
    if not field:
        return False
    lo, hi = bounds
    for part in field.split(','):
        match = _CRON_TOKEN_RE.match(part)
        if not match:
            return False
        base, range_part, step_part = match.group(1), match.group(2), match.group(3)
        if base == '*':
            if range_part is not None:
                return False  # "*-5" is not a token this grammar accepts
        else:
            base_n = int(base)
            if not (lo <= base_n <= hi):
                return False
            if range_part is not None:
                end_n = int(range_part[1:])
                if not (lo <= end_n <= hi) or end_n < base_n:
                    return False
        if step_part is not None and int(step_part[1:]) <= 0:
            return False
    return True


def _cron_is_valid(cron):
    if not isinstance(cron, str):
        return False
    fields = cron.split()
    if len(fields) != 5:
        return False
    return all(
        _cron_field_is_valid(field, bounds)
        for field, bounds in zip(fields, _CRON_FIELD_BOUNDS)
    )


# ---------------------------------------------------------------------------
# R9 (7): task_params must be publicly safe (this repo is public, docs/ai/
# core.md "公開情報と秘密情報"). task_params is otherwise treated as an
# opaque blob (R1) -- copied through untouched everywhere else in this
# module -- but R9(7) requires *reading* it once, at preflight, purely to
# look for secret candidates. A dedicated, ruleset-driven DLP engine
# already exists in this repo (roles/operator_request_channel/files/oprc/
# dlp.py) but is private library code belonging to a different role; this
# module intentionally does not import across role boundaries (that
# coupling decision was out of this task's scope -- see the implement
# record).
#
# This is an ALLOWLIST, not a denylist (rewritten 2026-08-09, independent
# review High #3). The first version rejected only values that *matched* a
# known-bad pattern (secret-looking key names, IPv4-looking strings, a few
# well-known token shapes) -- so anything that simply didn't match one of
# those patterns passed silently, including genuinely unclassifiable
# content (`environment='{"opaque":"not-classifiable-value"}'` was found
# to pass in review). That inverted R9's own instruction ("判定できない
# ときは停止する" -- unclassifiable must fail, not pass by default).
#
# The allowlist itself was widened once already (2026-08-09, same day):
# Coordinator fetched all 19 real schedules with a single GET each and ran
# them through this preflight. `params` turned out to be a *real* top-level
# key (requirement 6.5 already says the API accepts it; this repo's own
# catalog had simply never used it yet), and -- not documented anywhere in
# the requirement -- `environment`'s decoded JSON stores its 2 boolean-
# shaped keys (`force_renew`, `dry_run`) as the *strings* `"true"` /
# `"false"`, not native JSON booleans, while `params` (never JSON-string-
# encoded -- it is already a native dict on the raw object) stores the
# same keys with native types (`4`, `false`). The first version of this
# allowlist only accepted native bool/int/float, so it rejected 3 of the
# 19 real, already-running schedules -- the exact 3 that carry a non-empty
# `environment`. All 4 shapes actually seen across the 19 schedules are
# captured in the allowlist below and in scripts/tests/semaphore_
# schedules/_fixtures.py (`REAL_TASK_PARAMS_FIXTURES`).
#
#   16x  {"environment": "{}"}
#    1x  {"environment": "{\"force_renew\":\"false\"}"}
#    1x  {"environment": "{\"dry_run\":\"true\"}"}
#    1x  {"environment": "{\"dry_run\":\"true\"}",
#         "params": {"debug_level": 4, "dry_run": false}}
#
# The rule stays an allowlist, not a loosened denylist: only 2 top-level
# keys (`environment`, `params`), only 3 named keys inside either of them
# (`force_renew`, `dry_run`, `debug_level`), and only the specific value
# shapes actually observed for each (native bool/int/float everywhere,
# plus the literal strings `"true"`/`"false"` inside `environment` only,
# since that field's own values are observed to always be stringified).
# Anything else -- an unrecognized top-level key, an unrecognized nested
# key, a value of any other shape (an arbitrary string, a nested dict/list
# -- exactly what a secret, a token, or an internal hostname/IP would take)
# -- is rejected. Extending this further (e.g. a 4th named key, or letting
# `environment` carry non-boolean-shaped strings) is a deliberate,
# reviewed code change to the constants below, not something a catalog
# entry can opt into on its own.
#
# Findings never carry the value that triggered them -- only its location
# (a dict-path string) and the kind of problem -- because this repo is
# public and even a *rejected* value is exactly the kind of content that
# must not end up quoted inside a review document or error log. This
# mirrors the same non-negotiable rule roles/operator_request_channel/
# files/oprc/dlp.py already documents for itself ("Findings... never
# contain the string that matched -- only category, rule id, and JSON
# Pointer location"); this module does not import that module (a
# cross-role coupling decision out of this task's scope -- see the
# implement record) but follows the same discipline independently.
# ---------------------------------------------------------------------------

# The 2 task_params top-level keys observed with real data (2026-08-09,
# all 19 schedules): `environment` always, `params` on 1 of the 19.
_TASK_PARAMS_ALLOWED_TOP_LEVEL_KEYS = frozenset({'environment', 'params'})

# The only keys ever observed inside either `environment`'s decoded JSON or
# `params`'s native dict (requirement 6.5 + 2026-08-09 全19件実測).
_TASK_PARAM_ALLOWED_KEYS = frozenset({'force_renew', 'dry_run', 'debug_level'})

# `params` is a native dict on the raw object (not JSON-string-encoded) --
# its values observed so far are native bool/int, so only native
# bool/int/float are accepted here.
_PARAMS_ALLOWED_VALUE_TYPES = (bool, int, float)

# `environment`'s decoded values are observed to always be stringified
# (env-var semantics: an OS environment variable can only ever be a
# string) -- 2/19 real schedules store a boolean-shaped key as the exact
# string "true" or "false", never a native JSON boolean. Native bool/int/
# float are accepted too (the previous version of this allowlist already
# did, and no real data has ever needed to be walked back), so an API
# response that one day stops stringifying does not regress a schedule
# that previously passed. Any *other* string is not a recognized
# stringified primitive and is rejected -- this is not "strings are now
# allowed in environment", only these 2 exact literals are.
_ENVIRONMENT_BOOL_STRINGS = frozenset({'true', 'false'})


def _environment_value_is_allowed(value):
    if isinstance(value, _PARAMS_ALLOWED_VALUE_TYPES):
        return True
    return isinstance(value, str) and value in _ENVIRONMENT_BOOL_STRINGS


def _named_params_problems(parsed, path, value_is_allowed):
    """Shared allowlist walk for a *decoded* flat dict of the 3 known
    keys, used for both `environment` (after JSON-decoding the string)
    and `params` (already a native dict) -- the only difference between
    the two is which value shapes are accepted, passed in as `value_is_
    allowed`.
    """
    problems = []
    for key, value in parsed.items():
        key_str = key if isinstance(key, str) else "<{}>".format(type(key).__name__)
        sub_path = "{}.{}".format(path, key_str)
        if not isinstance(key, str) or key not in _TASK_PARAM_ALLOWED_KEYS:
            problems.append(
                "{} は許可されていないキー(現状 force_renew / dry_run / "
                "debug_level のみ許可)".format(sub_path)
            )
            continue
        if not value_is_allowed(value):
            problems.append(
                "{} の値の型 ({}) が許可されていない".format(sub_path, type(value).__name__)
            )
    return problems


def _environment_public_problems(environment):
    """`environment` is the *value* of task_params['environment'] -- a
    JSON string per the requirement's 2026-08-09 API measurement, decoded
    here only to look inside it (never returned; every other function in
    this module keeps passing the original string through untouched, R1).
    """
    path = 'task_params.environment'
    if not isinstance(environment, str):
        return ["{} が文字列でない(JSON文字列であるべき)".format(path)]
    if environment.strip() == '':
        return []
    try:
        parsed = json.loads(environment)
    except (TypeError, ValueError):
        return ["{} が JSON として解析できない".format(path)]
    if parsed == {}:
        return []
    if not isinstance(parsed, dict):
        return ["{} が JSON object でない".format(path)]
    return _named_params_problems(parsed, path, _environment_value_is_allowed)


def _params_public_problems(params):
    """`params` is the *value* of task_params['params'] -- already a
    native dict on the raw object (never JSON-string-encoded, unlike
    `environment`; 2026-08-09 実測).
    """
    path = 'task_params.params'
    if not isinstance(params, dict):
        return ["{} が dict でない".format(path)]
    return _named_params_problems(
        params, path, lambda value: isinstance(value, _PARAMS_ALLOWED_VALUE_TYPES)
    )


def _task_params_public_problems(task_params):
    """Returns a list of problem strings; empty means "matched the
    allowlist" (see the module comment above for what that allowlist is
    and why an unrecognized shape is rejected rather than passed).
    """
    if not isinstance(task_params, dict):
        return ["task_params が dict でない"]

    problems = []
    for key in task_params:
        if key not in _TASK_PARAMS_ALLOWED_TOP_LEVEL_KEYS:
            key_str = key if isinstance(key, str) else "<{}>".format(type(key).__name__)
            problems.append(
                "task_params.{} は許可されていないキー"
                "(現状 environment / params のみ許可)".format(key_str)
            )

    if 'environment' in task_params:
        problems.extend(_environment_public_problems(task_params['environment']))
    if 'params' in task_params:
        problems.extend(_params_public_problems(task_params['params']))

    return problems


def _catalog_entry_label(entry, idx):
    name = entry.get('name') if isinstance(entry, dict) else None
    if isinstance(name, str) and name:
        return "{!r}(カタログ{}件目)".format(name, idx + 1)
    return "カタログ{}件目".format(idx + 1)


def semaphore_schedules_preflight(catalog, observed_schedules, observed_templates, closed_world):
    """R9: all 7 preflight checks, run independently of one another so a
    failure in one never suppresses or short-circuits the others (every
    catalog entry is walked once per check, using `.get()` with no
    assumption that an earlier check already validated the entry's
    shape). Returns findings; never raises and never talks to a network --
    the caller (task side) decides what "1件でもerrorsがあれば書き込みを
    1件も発行しない" (R9's own opening sentence) means operationally.
    """
    errors = []

    # ⑤ 型と必須項目 -- catalog only (observed_* are trusted API responses).
    for idx, entry in enumerate(catalog):
        label = _catalog_entry_label(entry, idx)
        if not isinstance(entry, dict):
            errors.append("{} が dict でない: {!r}".format(label, entry))
            continue
        for field in _REQUIRED_CATALOG_FIELDS:
            if field not in entry:
                errors.append("{} に必須フィールド {!r} が無い".format(label, field))
        if 'name' in entry and not isinstance(entry.get('name'), str):
            errors.append("{} の name が文字列でない: {!r}".format(label, entry.get('name')))
        if 'template' in entry and not isinstance(entry.get('template'), str):
            errors.append("{} の template が文字列でない: {!r}".format(label, entry.get('template')))
        if 'cron' in entry and not isinstance(entry.get('cron'), str):
            errors.append("{} の cron が文字列でない: {!r}".format(label, entry.get('cron')))
        if 'active' in entry and not isinstance(entry.get('active'), bool):
            errors.append("{} の active が bool でない: {!r}".format(label, entry.get('active')))
        if 'task_params' in entry and not isinstance(entry.get('task_params'), dict):
            errors.append(
                "{} の task_params が dict でない: {!r}".format(label, entry.get('task_params'))
            )

    # Names actually usable by the remaining checks -- a malformed entry's
    # name (missing, or not a string) is already reported above by ⑤ and
    # must not also generate spurious ①/⑥ findings for the same entry.
    catalog_names = [
        entry.get('name') for entry in catalog
        if isinstance(entry, dict) and isinstance(entry.get('name'), str) and entry.get('name')
    ]
    valid_catalog_names = set(catalog_names)

    # ① カタログ内 schedule 名の重複
    dup_catalog_names = sorted({n for n in catalog_names if catalog_names.count(n) > 1})
    if dup_catalog_names:
        errors.append("カタログ内で schedule 名が重複している: {}".format(", ".join(dup_catalog_names)))

    # ② API 側 schedule 名の重複
    observed_names_raw = [row.get('name') for row in observed_schedules]
    observed_names = [n for n in observed_names_raw if isinstance(n, str) and n]
    dup_observed_names = sorted({n for n in observed_names if observed_names.count(n) > 1})
    if dup_observed_names:
        errors.append("API 側で schedule 名が重複している: {}".format(", ".join(dup_observed_names)))

    # ③ template 名の解決(0件・複数件の双方)
    template_ids = {}
    for entry in catalog:
        if not isinstance(entry, dict):
            continue
        name = entry.get('name')
        template_name = entry.get('template')
        if not isinstance(name, str) or not name or not isinstance(template_name, str):
            continue  # already reported by ⑤ above
        matches = [row for row in observed_templates if row.get('name') == template_name]
        if len(matches) == 1:
            template_ids[name] = matches[0].get('id')
        else:
            errors.append(
                "schedule {!r} が指す template {!r} の一致件数が {} 件"
                "(1件でなければならない)".format(name, template_name, len(matches))
            )

    # ④ cron 文字列の妥当性
    for entry in catalog:
        if not isinstance(entry, dict):
            continue
        name = entry.get('name')
        cron = entry.get('cron')
        if isinstance(cron, str) and not _cron_is_valid(cron):
            errors.append("schedule {!r} の cron が妥当でない: {!r}".format(name, cron))

    # ⑥ フェーズによる分岐(R6 移行期間 / R18 closed-world)
    unmanaged = [
        {'id': row.get('id'), 'name': row.get('name')}
        for row in observed_schedules
        if row.get('name') not in valid_catalog_names
    ]
    if closed_world:
        if unmanaged:
            errors.append(
                "closed-world だが管理外 schedule がある: {}".format(
                    ", ".join(sorted(u['name'] for u in unmanaged if u['name']))
                )
            )
    else:
        missing = sorted({n for n in catalog_names if n not in observed_names})
        if missing:
            errors.append(
                "移行期間だがカタログの name が API 側に実在しない: {}".format(", ".join(missing))
            )

    # ⑦ task_params が公開可能な値だけであること
    for entry in catalog:
        if not isinstance(entry, dict):
            continue
        name = entry.get('name')
        task_params = entry.get('task_params')
        if not isinstance(task_params, dict):
            continue  # already reported by ⑤ above
        for problem in _task_params_public_problems(task_params):
            errors.append("schedule {!r} の task_params: {}".format(name, problem))

    observed_by_name = {row.get('name'): row for row in observed_schedules}

    return {
        'errors': errors,
        'unmanaged': unmanaged,
        'template_ids': template_ids,
        'observed_by_name': observed_by_name,
    }


def semaphore_schedules_desired(entry, observed_detail, template_id, stage):
    """R8-2: the effective desired state for the 5 managed fields, for one
    reconcile stage.

    `entry` is a catalog row (R1's 5 logical fields). `observed_detail` is
    the single-GET raw object (R8) for the existing schedule, or None when
    this entry has no existing schedule yet. `template_id` is the id
    already resolved by semaphore_schedules_preflight (R3: never taken
    from the catalog).

    Stage 1 never activates (R8-3): a brand-new schedule is always
    created with active=False (R13); an existing schedule keeps its
    *observed* active value unless the catalog says False, in which case
    it is deactivated immediately (R8-2's "即時無効化"). Stage 2 is only
    ever invoked by a caller that has already re-confirmed every R12
    condition via semaphore_schedules_activation_gate -- this function has
    no way to check R12 itself -- so its desired active is unconditionally
    True.
    """
    if stage not in (1, 2):
        raise ValueError("stage must be 1 or 2, got {!r}".format(stage))

    desired = {
        'name': entry['name'],
        'cron_format': entry['cron'],
        'template_id': template_id,
        'task_params': entry['task_params'],
    }

    if stage == 2:
        desired['active'] = True
        return desired

    if observed_detail is None:
        desired['active'] = False  # R13
    elif entry.get('active') is False:
        desired['active'] = False  # R8-2: immediate true -> false
    else:
        desired['active'] = bool(observed_detail.get('active'))  # stage 1: never activates

    return desired


def semaphore_schedules_diff(catalog, observed_by_name, detail_by_id, template_ids):
    """Stage-1 diff (R8-3) plus the pending-activation report (R8-2).

    `observed_by_name` and `template_ids` are the same-named outputs of
    semaphore_schedules_preflight. `detail_by_id` maps a schedule id to its
    single-GET raw object (R8: the *only* legitimate merge source for a
    write; this function only reads it for comparison, it does not write).

    `stage1`'s membership (R8-2) is exactly "management-4-fields differ,
    or an immediate deactivation is needed" -- both fall out naturally
    from comparing `before` (the raw object's current 5 fields) against
    `desired` (stage-1's effective desired state, which itself never
    introduces true->false->true activation), so no separate branch is
    needed to keep activation out of `stage1`.

    `pending_activation` is independent of `stage1`/`unchanged` membership
    -- a schedule can be unchanged for stage 1 and still be pending
    activation (R8-3's step 2 case), or need a stage-1 write and also be
    pending activation.
    """
    new_items = []
    stage1_items = []
    unchanged_items = []
    pending_activation = []

    for entry in catalog:
        name = entry['name']
        template_id = template_ids.get(name)
        observed_row = observed_by_name.get(name)

        if observed_row is None:
            desired = semaphore_schedules_desired(entry, None, template_id, 1)
            new_items.append({'name': name, 'desired': desired})
            continue

        sched_id = observed_row.get('id')
        detail = detail_by_id.get(sched_id) or {}
        desired = semaphore_schedules_desired(entry, detail, template_id, 1)
        before = _management_fields_from_raw(detail)
        changed_fields = [
            field for field in _MANAGED_FIELD_ORDER
            if not _strict_equal(before.get(field), desired.get(field))
        ]

        if changed_fields:
            stage1_items.append({
                'name': name,
                'id': sched_id,
                'before': before,
                'after': desired,
                'fields': changed_fields,
            })
        else:
            unchanged_items.append(name)

        if entry.get('active') is True and detail.get('active') is not True:
            pending_activation.append({'name': name, 'id': sched_id})

    return {
        'new': new_items,
        'stage1': stage1_items,
        'unchanged': unchanged_items,
        'pending_activation': pending_activation,
    }


def semaphore_schedules_payload(raw_detail, desired):
    """R8: get-then-merge-then-send. Copies every field of the just-fetched
    single-GET raw object, then overwrites only the 5 managed fields with
    `desired` -- this is deliberately a shallow `dict(raw_detail)` copy,
    not a deep one: nested values (`task_params`, `repository_id`, ...)
    that are *not* overwritten are the caller's original objects, and the
    5 that are overwritten are replaced wholesale (never mutated in
    place), so aliasing is never observable from either side.
    """
    payload = dict(raw_detail)
    for field in _MANAGED_FIELD_ORDER:
        payload[field] = desired[field]
    return payload


def semaphore_schedules_create_payload(desired, project_id):
    """POST payload for a brand-new schedule (R13: `desired['active']` is
    always False here in practice, because callers only ever build
    `desired` for a new entry via stage 1). No get-then-merge applies --
    there is nothing to merge with yet -- so this is just the 5 managed
    fields (R8-2 renamed: `cron`/`template` -> `cron_format`/`template_id`)
    plus the `project_id` the catalog itself never carries (R4).
    """
    return {
        'name': desired['name'],
        'project_id': project_id,
        'template_id': desired['template_id'],
        'cron_format': desired['cron_format'],
        'task_params': desired['task_params'],
        'active': desired['active'],
    }


def semaphore_schedules_verify(raw_after, desired):
    """R16-2: post-write verification. Type-strict equality (`_strict_
    equal`) on the projected 5 fields -- no normalization, no leniency for
    "close enough" -- because R16-2 explicitly requires that a normalized
    or silently-dropped value (the API discards unknown `task_params`
    keys, per the requirement's 6.5 measurement) must be detected as a
    mismatch, never treated as a successful write.

    Deliberately scoped to only the 5 managed fields -- whether the *other*
    fields on the raw object also survived the write untouched is a
    separate question (AC4/AC17), answered by `semaphore_schedules_
    nonmanaged_diff` instead, not folded in here.
    """
    after = _management_fields_from_raw(raw_after)
    return [
        field for field in _MANAGED_FIELD_ORDER
        if not _strict_equal(after.get(field), desired.get(field))
    ]


def semaphore_schedules_nonmanaged_diff(before_raw, after_raw):
    """AC4 / AC17: "書き込み直後の単一 GET で、管理5項目以外の非管理
    フィールドが実行前と一致する" -- `semaphore_schedules_verify` only
    ever looks at the 5 managed fields (by design, R8-2), so a write that
    silently changes or drops something else on the object (`repository_
    id`, `delete_after_run`, `type`, ...) would otherwise pass unnoticed
    (2026-08-09 review High #2).

    `before_raw` is the single-GET raw object fetched immediately before
    the write (the same one `semaphore_schedules_payload` merged into,
    R8), `after_raw` is the single-GET raw object fetched immediately
    after. Compares the union of both objects' keys, minus the 5 managed
    fields, with the same type-strict equality as `verify` (a field
    present on only one side counts as changed, same as a field whose
    value differs). Returns the list of non-managed field names that
    changed; empty means every non-managed field was preserved exactly.
    """
    nonmanaged_keys = (set(before_raw.keys()) | set(after_raw.keys())) - set(_MANAGED_FIELD_ORDER)
    changed = []
    for key in sorted(nonmanaged_keys):
        before_has = key in before_raw
        after_has = key in after_raw
        if before_has != after_has or not _strict_equal(before_raw.get(key), after_raw.get(key)):
            changed.append(key)
    return changed


def semaphore_schedules_stage2_precheck(raw_detail, stage1_verified_desired):
    """R8-3: the check made immediately before issuing the stage-2
    (activation-only) PUT. Re-checks the 4 non-active managed fields
    against the value stage 1 already verified, and separately requires
    `active` to still be exactly False (R8-3: "第2段階の直前の単一 GET
    で...active が false であることを確認する") -- `active` is reported
    by name in the mismatch list precisely when it is not, so a caller
    that finds it non-empty knows both *that* something changed and,
    from the field names, roughly *what*.
    """
    current = _management_fields_from_raw(raw_detail)
    mismatched = [
        field for field in _STAGE1_FIELD_ORDER
        if not _strict_equal(current.get(field), stage1_verified_desired.get(field))
    ]
    if current.get('active') is not False:
        mismatched.append('active')
    return mismatched


def _normalize_api_base_url(url):
    """R15: absorb only notational differences (trailing slash, scheme/host
    case) -- never resolve or equate a different hostname. Query strings
    and fragments have no legitimate place in an API base URL in this
    repo's usage, so dropping them is not "equating an alias", it is
    discarding noise that was never part of the base URL's identity.
    """
    if not isinstance(url, str) or not url:
        return url
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip('/')
    return urlunsplit((scheme, netloc, path, '', ''))


def semaphore_schedules_activation_gate(
    api_base_url, canonical_url, allow_flag, closed_world,
    unmanaged_count, preflight_ids, current_ids,
):
    """R12 + R15 + R16: whether `false -> true` activation may proceed at
    all, independent of any single schedule. All 5 conditions are checked
    unconditionally and independently (never short-circuited), so
    `reasons` always lists every condition that is currently unmet -- this
    is deliberately an allowlist (R15: "「ansy でなければ許可」という
    否定判定にしない"), so a canonical-URL mismatch is itself a reason,
    never the default-permit path.

    `allow_flag` and `closed_world` must be actual `bool` values, not
    merely truthy/falsy. `ansible-playbook -e key=value` values are
    strings -- `-e semaphore_schedules_allow_activation=false` arrives
    here as the non-empty string `"false"`, which bare `if not
    allow_flag:` would treat as *true* (2026-08-09 review Critical #1,
    reproduced: `allow_flag="false" closed_world="true"` -> `allowed:
    True`). A non-bool is therefore treated as its own, distinct failure
    -- fail-closed, not "coerce and hope" -- so a caller can tell a type
    mistake apart from a legitimate "not yet closed-world" / "not
    explicitly allowed" outcome. Task-side callers are expected to also
    validate these at the entry point (`| bool` with strict typing, or
    equivalent) -- this function's own check is the last line of defense,
    not a substitute for that.
    """
    reasons = []

    if not isinstance(closed_world, bool):
        reasons.append(
            "closed_world が真偽値でない(型: {}) -- 設定ミスとして有効化を許可しない"
            "(R12条件1)".format(type(closed_world).__name__)
        )
    elif not closed_world:
        reasons.append("移行期間のため有効化しない(R12条件1: closed-worldのみ)")

    if unmanaged_count:
        reasons.append(
            "管理外 schedule が {} 件あるため有効化しない(R12条件2)".format(unmanaged_count)
        )

    if not isinstance(allow_flag, bool):
        reasons.append(
            "allow_flag が真偽値でない(型: {}) -- 設定ミスとして有効化を許可しない"
            "(R12条件3)".format(type(allow_flag).__name__)
        )
    elif not allow_flag:
        reasons.append("有効化が実行ごとに明示許可されていない(R12条件3)")

    normalized_used = _normalize_api_base_url(api_base_url)
    normalized_canonical = _normalize_api_base_url(canonical_url)
    url_matches = bool(normalized_canonical) and normalized_used == normalized_canonical
    if not url_matches:
        reasons.append(
            "接続先 URL {!r} が canonical な本番 URL {!r} と一致しない"
            "(R15 allowlist: 一致するときだけ許可)".format(api_base_url, canonical_url)
        )

    if set(preflight_ids) != set(current_ids):
        reasons.append("preflight 時点から schedule 集合が変化しているため有効化しない(R16)")

    return {
        'allowed': not reasons,
        'reasons': reasons,
        'url_used': normalized_used,
    }


class FilterModule(object):
    def filters(self):
        return {
            'semaphore_schedules_preflight': semaphore_schedules_preflight,
            'semaphore_schedules_diff': semaphore_schedules_diff,
            'semaphore_schedules_desired': semaphore_schedules_desired,
            'semaphore_schedules_payload': semaphore_schedules_payload,
            'semaphore_schedules_create_payload': semaphore_schedules_create_payload,
            'semaphore_schedules_verify': semaphore_schedules_verify,
            'semaphore_schedules_nonmanaged_diff': semaphore_schedules_nonmanaged_diff,
            'semaphore_schedules_stage2_precheck': semaphore_schedules_stage2_precheck,
            'semaphore_schedules_activation_gate': semaphore_schedules_activation_gate,
        }
