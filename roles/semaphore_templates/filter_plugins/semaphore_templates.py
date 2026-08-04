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


def _target_fields(entry):
    return {
        'name': semaphore_templates_render_name(entry),
        'playbook': entry['playbook'],
        'arguments': entry.get('arguments') or [],
        'survey_vars': entry.get('survey_vars') or [],
        'description': semaphore_templates_build_marker(entry['playbook'], entry.get('variant')),
    }


def _observed_fields(observed_row):
    # Must mirror _target_fields()'s key set exactly (including 'playbook')
    # -- otherwise `before != target` is true even when nothing actually
    # differs, and AC1 idempotency never holds (a real bug caught this way
    # once already, before `description` existed as a field; see the
    # implement record §8 of the original pass).
    return {
        'name': observed_row.get('name'),
        'playbook': observed_row.get('playbook'),
        'arguments': observed_row.get('arguments') or [],
        'survey_vars': observed_row.get('survey_vars') or [],
        'description': observed_row.get('description') or '',
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


class FilterModule(object):
    def filters(self):
        return {
            'semaphore_templates_render_name': semaphore_templates_render_name,
            'semaphore_templates_reconcile': semaphore_templates_reconcile,
            'semaphore_templates_build_marker': semaphore_templates_build_marker,
        }
