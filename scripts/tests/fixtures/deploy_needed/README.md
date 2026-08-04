# Fixtures for `scripts/check-deploy-needed.py`

`check-deploy-needed.py` reads staged content from the **git index**
(`git show :<path>`, `git diff --cached`, `git ls-files`) — the same
convention `scripts/check-doc-consistency.py` uses (see
`scripts/tests/fixtures/README.md`, one directory up). This directory
follows the identical pattern that fixture set established, nested under
`scripts/tests/fixtures/` (rather than a `.gitignore`-blocked sibling of it
— `scripts/tests/*` is ignored except for the `scripts/tests/fixtures/`
subtree specifically) but kept in its own `deploy_needed/` subdirectory
since these fixtures exercise a different script with a different input
(staged diff, not the whole tracked tree) — see
`docs/ai/reviews/deploy_awareness/2026-08-04_002_implement.md`.

The fixtures below are **plain file trees with no `.git` of their own** —
tracked in this repository like any other file. Running
`check-deploy-needed.py --repo-root` directly against one will fail with
"not a git working tree" (by design). To actually exercise a fixture, use
`run-fixture-checks.sh`, which copies each fixture into a throwaway temp
directory, runs `git init` + `git add -A` there (no commit — with zero
prior commits, `git diff --cached` against the empty tree reports every
fixture file as staged, which is exactly the "I just changed this" state
each fixture wants to simulate), runs the checker against that temp copy,
and deletes it afterward:

```sh
scripts/tests/fixtures/deploy_needed/run-fixture-checks.sh
```

This is the reproduction procedure for R7
(`docs/ai/reviews/deploy_awareness/2026-08-04_001_requirement.md`), covering
AC4 / AC5 / AC6 / AC8, plus `r9_run_host_override/` added for the 2026-08-04
R9 addendum (not tied to a numbered AC — R9 amended R4/R3/JSON to share one
`-l` value instead of adding a new acceptance criterion).

2026-08-05 added a second, unrelated set of fixtures for
`docs/ai/reviews/precommit_checks_extension/2026-08-05_001_requirement.md`
(R1: new-playbook Semaphore-template advisory; R2: staged-list retrieval
unification) — see the two tables below.

## Fixtures (R7, deploy_awareness)

| Fixture | Exercises | Expected result |
| --- | --- | --- |
| `ac4_catalog_file_changed/` | AC4 (R4) | `exit 0`; stdout contains `` 配備が要る: `playbooks/incident_investigate_setup.yml`(quory) `` |
| `ac5_unrelated_change/` | AC5 | `exit 0`; stdout contains no `配備が要る` line at all (only `docs/note.md` is staged, and the catalog's referenced source file is deliberately absent from the tree) |
| `ac6_missing_playbook/` | AC6 (R5) | `exit 1`; stdout names the broken catalog entry, `playbooks/does_not_exist_setup.yml` |
| `ac8_template_changed/` | AC8 (R6) | `exit 0`; stdout contains a separate `配備が要る可能性` heading (Tier 2, distinct from AC4's catalog-verified heading) for `roles/incident_investigate/templates/incident-investigate.json.j2` |
| `r9_run_host_override/` | R9 | `exit 0`; the entry's `hosts: [authy, monnie]` but `run_host: quory` -- stdout must show `` (quory) `` and must NOT show `` (authy, monnie) ``, proving `run_host` wins over the raw `hosts:` list in R4's output |

## Fixtures (R1, precommit_checks_extension, 2026-08-05)

These exercise `check_new_playbook_catalog_advisory()` — a newly *added*
`playbooks/*.yml` with no matching `playbook:` entry in
`roles/semaphore_templates/defaults/main.yml`'s `semaphore_templates_catalog`.
Advisory only; all three expect `exit 0`.

| Fixture | Exercises | Expected result |
| --- | --- | --- |
| `newplaybook_ac1_no_catalog_entry/` | AC1 | stdout contains the `新規playbookにSemaphoreボタンがありません` heading and `` `playbooks/new_thing.yml` `` |
| `newplaybook_ac2_has_catalog_entry/` | AC2 | stdout contains no `Semaphoreボタンがありません` text — the catalog already names `playbooks/new_thing.yml` |
| `newplaybook_ac3_existing_modified/` | AC3 | stdout contains no `Semaphoreボタンがありません` text — only the *content* of an already-committed `playbooks/existing_thing.yml` changed (git status `M`), it was not added; uses the before/after layout below since this distinction cannot exist with zero prior commits |

`newplaybook_ac3_existing_modified/` uses a **before/after** layout instead
of the flat-tree layout every other fixture here uses: `before/` is
committed first (`git init` + `git add -A` + `git commit`), then `after/` is
laid on top and staged. This is what makes `--diff-filter=A` correctly see
the difference between "this path did not exist before" (Added) and "this
path's content changed" (Modified) — the flat-tree layout's zero-prior-commit
trick makes every file trivially "Added" and cannot represent AC3 at all.
`run-fixture-checks.sh` knows which fixtures need this via the
`before_after_fixtures` array near its top; add a fixture name there if a
future fixture needs the same layout.

`run-fixture-checks.sh` also runs two more checks after the table-driven
loop, not tied to a single named fixture directory because they cannot be
represented as tracked files (see the script's own comments for why):

- **`ac4_quoted_path_parity`** (AC4): builds a throwaway repo with a
  filename containing a literal backslash and confirms *both*
  `git-pre-commit-check.sh` and `check-deploy-needed.py` (self-derived,
  no `--staged-paths`) fail closed on it — proving the two sides make the
  same judgment about an unsafe path.
- **`ac4_given_staged_paths_is_authoritative`** (AC4): proves
  `--staged-paths`, once given, is actually used instead of
  `check-deploy-needed.py` re-deriving the list from git itself — a path fed
  in via `--staged-paths` that was never really staged still drives an R4
  match, while the same repo checked without `--staged-paths` does not
  match it.

`run-fixture-checks.sh` has the fixture table (exit code + required/forbidden
substrings) built in, plus hardcoded expectations for the two checks above,
and fails loudly if any fixture's or check's actual behavior stops matching.

Each fixture carries only the minimal catalog shape(s)
(`roles/deployment_drift_check/defaults/main.yml`, and for the R1 fixtures
also `roles/semaphore_templates/defaults/main.yml`) and playbook stand-ins
the scripts actually read — not a full copy of the real catalogs — so a
fixture failure always points at this script's logic, not at production
catalog drift.

## Editing a fixture

Just edit the files directly; there is no index to keep in sync since these
are plain trees, not git repos (except `newplaybook_ac3_existing_modified/`'s
`before/`, which is committed into a *throwaway* repo at run time only —
still nothing to keep in sync by hand). `run-fixture-checks.sh` builds the
throwaway index fresh on every run.
