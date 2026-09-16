"""Semaphore templates as code: naming (R2) and reconciliation (R3/R11) logic.

Pure Python, no Ansible-only APIs — this is deliberate. It lets this logic be
exercised with plain python3 against fixture data (see docs/ai/reviews/
semaphore_templates_as_code/2026-08-04_003_implement.md for the
self-verification transcript), with no network, no become, and no host in
the loop. This matters doubly now: even with ansy available for empirical
API verification (2026-08-04 requirement addendum), Implementer still has no
standing to touch a real host at all (docs/ai/roles/implementer.md — real
host verification, including read-only checks, is Tester's role; a task
briefing cannot broaden a Role's real-host reach, docs/ai/core.md
"subagentが共通して守ること"). The logic below is designed to be *correct
regardless* of two things this session could not itself confirm empirically
(see the 2026-08-04 addendum to the implement record for what that means in
practice and what is asked of whoever runs the first real apply).

Naming rule: docs/ai/reviews/semaphore_templates_as_code/
2026-08-04_001_requirement.md R2.
Identification rule (R3/R11, 2026-08-04 addendum): identify by (playbook,
variant), and — after the 2026-08-04 addendum — store that identity *inside*
the Semaphore object itself (its `description` field), not in a side file.
The previous design (`legacy_name` + a local state file on quory) is exactly
the "two sources of truth" structure Critical #1 of the independent review
(2026-08-04_004_review.md) found broken: losing the side file made every
entry look brand new, because nothing about the Semaphore object itself
still pointed back to the catalog. This version removes the side file
entirely. The object's own `description` is the *only* place the mapping is
kept; a lost local file can no longer desynchronize it from reality, because
there no longer is a second place for it to live.
"""
from __future__ import annotations

import re
import json
from datetime import datetime, timezone

# The exact, and only, content this role ever writes to `description`. No
# human-authored text is expected to coexist here — R1 does not define
# `description` as a catalog field, and after the 2026-08-04 addendum R11
# calls it "a managed field" once adopted. Keeping the marker format dead
# simple (one prefix, one separator) makes the parse total and unambiguous;
# anything that doesn't start with the prefix is simply "not ours" (an
# orphan, R5) rather than a parse failure.
_MARKER_PREFIX = "semaphore-templates:playbook="
_MARKER_VARIANT_SEP = " variant="


def semaphore_templates_render_name(entry):
    """R2: name = "{class}: {title}{ (variant)}".

    ``title`` defaults to the playbook basename with ``.yml`` stripped,
    ``_`` turned into spaces, and the first character capitalized (the rest
    of the string is left as produced by the substitution — every playbook
    basename in this repo is already lowercase, so this matches
    ``str.capitalize()`` without also lowercasing intentional casing inside
    an explicit ``title`` override, which never goes through this branch).
    """
    title = entry.get('title')
    if not title:
        base = entry['playbook'].rsplit('/', 1)[-1]
        if base.endswith('.yml'):
            base = base[:-4]
        title = base.replace('_', ' ')
        if title:
            title = title[0].upper() + title[1:]
    name = "{}: {}".format(entry['class'], title)
    variant = entry.get('variant')
    if variant:
        name += " ({})".format(variant)
    return name


def semaphore_templates_button_names(catalog, playbook):
    """R10-a: rendered Semaphore template name(s) whose catalog entry's
    ``playbook`` matches the given playbook path, in catalog order.

    Returns a plain list — 0, 1, or more names. This filter only looks up
    and renders; it makes no decision about what an empty or multi-item
    result means. The caller (deployment_drift_check's report.yml) decides:
    0 matches falls back to the pre-existing `ansible-playbook ... -l ...`
    line (the finding's playbook has no Semaphore button at all — e.g.
    playbooks/knowledge_review_timer.yml, an ansy timer with no Semaphore
    counterpart), and more than 1 lists every candidate rather than guessing
    which variant the operator wants (R10-a, requirement
    2026-08-04_008_requirement_p1.md).
    """
    return [
        semaphore_templates_render_name(entry)
        for entry in catalog
        if entry.get('playbook') == playbook
    ]


def _catalog_key(entry):
    """R3 identification key. '-' stands in for "no variant" so every
    catalog entry — shared-playbook or not — has a key of the same shape.
    """
    return "{}#{}".format(entry['playbook'], entry.get('variant') or '-')


def semaphore_templates_build_marker(playbook, variant=None):
    """R11: the exact `description` value this role assigns to an object it
    owns. Deliberately a pure function (both filter_plugins entry points and
    the reconcile logic share it) so encode/decode can never drift apart.
    """
    marker = "{}{}".format(_MARKER_PREFIX, playbook)
    marker += "{}{}".format(_MARKER_VARIANT_SEP, variant or "")
    return marker


def _parse_marker(description):
    """Inverse of semaphore_templates_build_marker(). Returns (playbook,
    variant_or_None) if `description` is a marker this role wrote, else
    None (covers: empty, hand-authored text, or a marker for a playbook
    that no longer exists in the catalog — all "not a match", never an
    error to raise).
    """
    if not description or not isinstance(description, str):
        return None
    if not description.startswith(_MARKER_PREFIX):
        return None
    rest = description[len(_MARKER_PREFIX):]
    if _MARKER_VARIANT_SEP not in rest:
        return None
    playbook, _, variant = rest.partition(_MARKER_VARIANT_SEP)
    if not playbook:
        return None
    return playbook, (variant or None)


def semaphore_templates_preflight(catalog, observed, max_creates):
    """Validate the complete template read-set and bound its create set."""
    errors = []
    if catalog and not observed:
        errors.append("template一覧が空だがカタログは非空")
    identities = set()
    for index, row in enumerate(observed):
        label = row.get('name') if isinstance(row, dict) else None
        prefix = "template {!r} (API行{})".format(label, index + 1)
        if not isinstance(row, dict):
            errors.append("{}: row がmappingでない".format(prefix))
            continue
        if isinstance(row.get('id'), bool) or not isinstance(row.get('id'), int):
            errors.append("{}: id が整数でない".format(prefix))
        description = row.get('description')
        if description is not None and not isinstance(description, str):
            errors.append("{}: description の型が不正".format(prefix))
        elif isinstance(description, str) and description.startswith(_MARKER_PREFIX):
            marker = _parse_marker(description)
            if marker is None:
                errors.append("{}: description marker が不正".format(prefix))
            else:
                key = marker[0], marker[1] or '-'
                if key in identities:
                    errors.append("{}: identity {!r} が重複".format(prefix, key))
                identities.add(key)
        elif isinstance(row.get('name'), str):
            # A markerless row that collides with a rendered catalog name is
            # ambiguous: it may be an unmanaged duplicate or a managed row
            # whose marker was lost in a partial response. Never create over it.
            for entry in catalog:
                if not isinstance(entry, dict) or not isinstance(entry.get('class'), str) or not isinstance(entry.get('playbook'), str):
                    continue
                if semaphore_templates_render_name(entry) == row['name'] and entry.get('legacy_name') != row['name']:
                    errors.append("{}: markerless name collides with catalog target; lost marker/duplicate is ambiguous".format(prefix))
                    break
        for field, types in (('name', (str,)), ('playbook', (str,)),
                             ('arguments', (str, list, bool, type(None))),
                             ('survey_vars', (str, list, bool, type(None))),
                             ('description', (str, type(None)) )):
            if field in row and not isinstance(row[field], types):
                errors.append("{}: {} の型が不正".format(prefix, field))
        for field in ('arguments', 'survey_vars'):
            if row.get(field) is True:
                errors.append("{}: {} の true は正規化表で未定義".format(prefix, field))
    creates = semaphore_templates_create_count(catalog, observed)
    if creates > max_creates:
        errors.append("template新規作成 {} 件が上限 {} 件を超過".format(creates, max_creates))
    return errors


def semaphore_templates_create_count(catalog, observed):
    creates = 0
    for entry in catalog:
        if not isinstance(entry, dict):
            continue
        marker_match = any(_parse_marker(r.get('description')) ==
                           (entry.get('playbook'), entry.get('variant') or None)
                           for r in observed if isinstance(r, dict))
        legacy_match = bool(entry.get('legacy_name')) and any(
            isinstance(r, dict) and r.get('name') == entry.get('legacy_name')
            and _parse_marker(r.get('description')) is None for r in observed)
        if not marker_match and not legacy_match:
            creates += 1
    return creates


def _json_or_native(value, path, label, allowed_native):
    if isinstance(value, str):
        import json
        try:
            value = json.loads(value) if value else []
        except (ValueError, TypeError) as exc:
            raise ValueError("{} {}: JSON不正 ({})".format(label, path, exc))
    if not isinstance(value, allowed_native):
        raise ValueError("{} {}: 型が不正 ({})".format(label, path, type(value).__name__))
    return value


def _target_fields(entry):
    label = semaphore_templates_render_name(entry)
    arguments = entry.get('arguments', [])
    survey = entry.get('survey_vars', [])
    if arguments is None or arguments is False:
        arguments = []
    if survey is None or survey is False:
        survey = []
    if not isinstance(arguments, list) or not isinstance(survey, list):
        raise ValueError("{} arguments / survey_vars: 型が不正".format(label))
    return {
        'name': label,
        'playbook': entry['playbook'],
        'arguments': arguments,
        'survey_vars': _normalize_survey(survey, label),
        'description': semaphore_templates_build_marker(entry['playbook'], entry.get('variant')),
    }


def _normalize_survey(value, label):
    if not isinstance(value, list):
        raise ValueError("{} survey_vars: listでない".format(label))
    out = []
    for i, item in enumerate(value):
        path = "survey_vars[{}]".format(i)
        if not isinstance(item, dict):
            raise ValueError("{} {}: mappingでない".format(label, path))
        normalized = dict(item)
        for field in ('name', 'title', 'type', 'description'):
            if field in normalized and not isinstance(normalized[field], str):
                raise ValueError("{} {}.{}: stringでない".format(label, path, field))
        if 'values' in normalized:
            if not isinstance(normalized['values'], list) or any(not isinstance(v, dict) for v in normalized['values']):
                raise ValueError("{} {}.values: mappingのlistでない".format(label, path))
        if 'required' in normalized:
            if not isinstance(normalized['required'], bool):
                raise ValueError("{} {}.required: boolでない".format(label, path))
            if normalized['required'] is False:
                normalized.pop('required')
        if 'default_value' in normalized:
            if not isinstance(normalized['default_value'], str):
                raise ValueError("{} {}.default_value: stringでない".format(label, path))
            if normalized['default_value'] == '':
                normalized.pop('default_value')
        out.append(normalized)
    return out


def _observed_fields(observed_row):
    # Must mirror _target_fields()'s key set exactly (including 'playbook')
    # -- otherwise `before != target` is true even when nothing actually
    # differs, and AC1 idempotency never holds (a real bug caught this way
    # once already, before `description` existed as a field; see the
    # implement record §8 of the original pass).
    return {
        'name': observed_row.get('name'),
        'playbook': observed_row.get('playbook'),
        'arguments': ([] if observed_row.get('arguments') is False or observed_row.get('arguments') is None
                      else _json_or_native(observed_row.get('arguments', []), 'arguments', observed_row.get('name'), (list,))),
        'survey_vars': _normalize_survey(
            [] if observed_row.get('survey_vars') is False or observed_row.get('survey_vars') is None
            else _json_or_native(observed_row.get('survey_vars', []), 'survey_vars', observed_row.get('name'), (list,)),
            observed_row.get('name')),
        'description': observed_row.get('description', ''),
    }


def semaphore_templates_reconcile(catalog, observed):
    """R3/R11: identify existing templates by a marker this role itself
    wrote into their `description` — never by `name`, and never via a file
    that lives anywhere other than inside the Semaphore object being
    tracked.

    Args:
      catalog:  list of definition entries (this repo's desired state, R1).
      observed: list of dicts {id, name, playbook, arguments, survey_vars,
                description} — the current state read from the Semaphore
                API for every existing template (R11 requires this be the
                single source of truth for identity; no side state is
                threaded through this function at all — contrast the
                pre-addendum signature, which took a third `state` arg).

    Matching, in order:
      1. An observed row's `description` decodes (via `_parse_marker`) to
         this entry's own (playbook, variant) -> that row is *the* existing
         template for this entry, unconditionally. This is the only path
         used from the second run onward.
      2. Otherwise (no row carries this entry's marker yet) and the entry
         carries a `legacy_name` (only the 34 entries transcribed from the
         2026-08-04 observation have one, since only they predate this
         role) -> match the observed row, not already claimed by another
         key and not itself already carrying *some other* marker, whose
         *current* `name` equals `legacy_name` exactly. This is the
         one-time bridge from "identified by hand-typed name" to
         "identified by an embedded marker": the very apply that matches
         this way also writes the marker (apply.yml), so it is not
         consulted again for this key on any later run.
      3. Otherwise -> no existing template; this is genuinely new (the
         normal path for the 9 setup playbooks R7 adds, which have no
         legacy_name at all).

    Returns a dict with:
      new       - entries to create (no existing template found)
      changed   - entries to update in place (existing id, fields differ —
                  including the case where `description` itself doesn't
                  carry the marker yet, i.e. the legacy_name bootstrap case,
                  which always counts as "changed" so the marker actually
                  gets written)
      unchanged - entries already matching, marker included (AC1 idempotency)
      orphans   - existing Semaphore templates matched by no catalog entry
                  (R5: report only, never delete). Includes objects whose
                  `description` looks like a marker for a (playbook,
                  variant) that is no longer in the catalog at all (e.g. a
                  catalog entry was deleted outright) — these are still
                  "ours" historically but unmatched today, and R5 forbids
                  deleting them just the same as any other orphan.
    """
    by_marker_key = {}
    for row in observed:
        parsed = _parse_marker(row.get('description'))
        if parsed is None:
            continue
        marker_key = "{}#{}".format(parsed[0], parsed[1] or '-')
        # First row wins on a duplicate marker (should not happen if this
        # role is the only writer of the prefix; not treated as fatal here
        # because a duplicate does not risk data loss — the second row
        # simply falls through to legacy_name matching or ends up an
        # orphan, both of which are safe, reportable outcomes).
        by_marker_key.setdefault(marker_key, row)

    claimed_ids = set()
    new_items = []
    changed_items = []
    unchanged_items = []

    for entry in catalog:
        key = _catalog_key(entry)
        target = _target_fields(entry)

        existing = by_marker_key.get(key)
        note = None

        if existing is None and entry.get('legacy_name'):
            for row in observed:
                if row['id'] in claimed_ids:
                    continue
                if _parse_marker(row.get('description')) is not None:
                    continue  # already "ours" for a different key; not eligible
                if row.get('name') == entry['legacy_name']:
                    existing = row
                    break
            if existing is None:
                note = (
                    "legacy_name {!r} に一致する既存テンプレートが見つからない"
                    "。新規作成として扱う".format(entry['legacy_name'])
                )

        if existing is not None:
            claimed_ids.add(existing['id'])
            before = _observed_fields(existing)
            if before != target:
                changed_items.append({
                    'key': key,
                    'id': existing['id'],
                    'before': before,
                    'after': target,
                })
            else:
                unchanged_items.append({'key': key, 'id': existing['id']})
        else:
            item = {'key': key, 'target': target}
            if note:
                item['note'] = note
            new_items.append(item)

    orphans = [row for row in observed if row['id'] not in claimed_ids]

    return {
        'new': new_items,
        'changed': changed_items,
        'unchanged': unchanged_items,
        'orphans': orphans,
    }


def semaphore_templates_orphan_baseline_diff(orphans, baseline):
    """Validate and compare normalized orphan identities as a sorted list."""
    errors = []

    def normalize(name, playbook, label):
        if not isinstance(name, str) or not isinstance(playbook, str):
            errors.append("{}: name/playbook が文字列でない".format(label))
            return None
        clean_name = re.sub(r'\s+', ' ', name.strip())
        clean_playbook = playbook[2:] if playbook.startswith('./') else playbook
        if not clean_name or not clean_playbook:
            errors.append("{}: 正規化後のname/playbookが空".format(label))
            return None
        return {'name': clean_name, 'playbook': clean_playbook}

    if not isinstance(baseline, list):
        errors.append("orphan baseline がlistでない")
        baseline = []
    normalized_baseline = []
    for idx, item in enumerate(baseline):
        if not isinstance(item, dict) or 'name' not in item or 'playbook' not in item:
            errors.append("orphan baseline[{}] にname/playbookが無い".format(idx))
            continue
        value = normalize(item['name'], item['playbook'], "orphan baseline[{}]".format(idx))
        if value is not None:
            normalized_baseline.append(value)

    normalized_orphans = []
    if not isinstance(orphans, list):
        errors.append("observed orphans がlistでない")
        orphans = []
    for idx, item in enumerate(orphans):
        if not isinstance(item, dict) or 'name' not in item or 'playbook' not in item:
            errors.append("orphan[{}] にname/playbookが無い".format(idx))
            continue
        value = normalize(item['name'], item['playbook'], "orphan[{}]".format(idx))
        if value is not None:
            normalized_orphans.append(value)

    key = lambda item: (item['name'], item['playbook'])
    actual = sorted(normalized_orphans, key=key)
    expected = sorted(normalized_baseline, key=key)
    return {'errors': errors, 'actual': actual, 'expected': expected, 'changed': actual != expected}


def semaphore_reconcile_marker_freshness(content, exists, is_regular_file, now_iso=None):
    """Return stale status for the latest-success marker; malformed is stale."""
    result = {'stale': True, 'error': None, 'age_seconds': None}
    if not exists:
        result['error'] = 'markerが欠落'
        return result
    if not is_regular_file:
        result['error'] = 'markerが通常ファイルでない'
        return result
    try:
        marker = json.loads(content)
        if not isinstance(marker, dict):
            raise ValueError('JSON rootがobjectでない')
        completed_at = marker.get('completed_at')
        if not isinstance(completed_at, str):
            raise ValueError('completed_atが文字列でない')
        completed = datetime.fromisoformat(completed_at)
        if completed.tzinfo is None:
            raise ValueError('completed_atにtimezoneが無い')
        now = datetime.fromisoformat(now_iso) if now_iso else datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError('nowにtimezoneが無い')
        age = (now.astimezone(timezone.utc) - completed.astimezone(timezone.utc)).total_seconds()
        result['age_seconds'] = age
        result['stale'] = age < 0 or age >= 24 * 60 * 60
        if age < 0:
            result['error'] = 'completed_atが未来'
        return result
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        result['error'] = 'JSON/時刻不正: {}'.format(exc)
        return result


def semaphore_reconcile_marker_actual(freshness):
    """Return useful finding text: elapsed seconds when known, otherwise cause."""
    if not isinstance(freshness, dict):
        return '鮮度を判定できません'
    age = freshness.get('age_seconds')
    if isinstance(age, (int, float)) and not isinstance(age, bool):
        return '{:g} seconds'.format(age)
    error = freshness.get('error')
    return error if isinstance(error, str) and error else '経過時間を判定できません'


class FilterModule(object):
    def filters(self):
        return {
            'semaphore_templates_render_name': semaphore_templates_render_name,
            'semaphore_templates_reconcile': semaphore_templates_reconcile,
            'semaphore_templates_orphan_baseline_diff': semaphore_templates_orphan_baseline_diff,
            'semaphore_reconcile_marker_freshness': semaphore_reconcile_marker_freshness,
            'semaphore_reconcile_marker_actual': semaphore_reconcile_marker_actual,
            'semaphore_templates_build_marker': semaphore_templates_build_marker,
            'semaphore_templates_button_names': semaphore_templates_button_names,
            'semaphore_templates_preflight': semaphore_templates_preflight,
            'semaphore_templates_create_count': semaphore_templates_create_count,
        }
