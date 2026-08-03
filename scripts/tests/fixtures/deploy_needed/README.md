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

## Fixtures

| Fixture | Exercises | Expected result |
| --- | --- | --- |
| `ac4_catalog_file_changed/` | AC4 (R4) | `exit 0`; stdout contains `` 配備が要る: `playbooks/incident_investigate_setup.yml`(quory) `` |
| `ac5_unrelated_change/` | AC5 | `exit 0`; stdout contains no `配備が要る` line at all (only `docs/note.md` is staged, and the catalog's referenced source file is deliberately absent from the tree) |
| `ac6_missing_playbook/` | AC6 (R5) | `exit 1`; stdout names the broken catalog entry, `playbooks/does_not_exist_setup.yml` |
| `ac8_template_changed/` | AC8 (R6) | `exit 0`; stdout contains a separate `配備が要る可能性` heading (Tier 2, distinct from AC4's catalog-verified heading) for `roles/incident_investigate/templates/incident-investigate.json.j2` |
| `r9_run_host_override/` | R9 | `exit 0`; the entry's `hosts: [authy, monnie]` but `run_host: quory` -- stdout must show `` (quory) `` and must NOT show `` (authy, monnie) ``, proving `run_host` wins over the raw `hosts:` list in R4's output |

`run-fixture-checks.sh` has this exact table (exit code + required/forbidden
substrings) built in and fails loudly if any fixture's actual behavior stops
matching it.

Each fixture carries only the minimal catalog shape
(`roles/deployment_drift_check/defaults/main.yml`) and playbook stand-ins
`check-deploy-needed.py` actually reads — not a full copy of the real
catalog — so a fixture failure always points at this script's logic, not at
production catalog drift.

## Editing a fixture

Just edit the files directly; there is no index to keep in sync since these
are plain trees, not git repos. `run-fixture-checks.sh` builds the
throwaway index fresh on every run.
