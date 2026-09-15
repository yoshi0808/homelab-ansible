# Phase 1 implementation record

Date: 2026-09-15

## Scope and decisions

Implemented the Phase 1 read-set checks and comparison normalization only. Phase 2 (daily apply, active separation, notifications, and liveness monitoring) was not implemented.

Normalization table (the filter plugin is the sole normalization/validation owner; `tasks/read.yml` now retains API values without coercion):

| Field | Accepted input | Canonical form / equivalence | Rejected |
|---|---|---|---|
| `arguments` | JSON string, list, `false`, `null` | JSON decoded list; `false`/`null` equal `[]` | malformed JSON, mapping, `true`, other scalar |
| `survey_vars` | JSON string, list of mappings, `false`, `null` | decoded list; absent/empty string/`false`/`null` equal `[]` | malformed JSON, mapping, `true`, other scalar, non-mapping list item |
| survey `required` | bool or absent | `false` equals absent | every non-bool value |
| survey `default_value` | string or absent | `""` equals absent | non-string |
| survey `name`, `title`, `type`, `description` | string or absent | preserved exactly | non-string |
| survey `values` | list of mappings or absent | preserved exactly; `{}` is not equated with `[]` | non-list or non-mapping element |
| template `description` | string, `null`, or absent | valid managed marker is parsed; non-marker text/empty/missing description remains unmanaged/orphan-eligible | non-string/non-null value; malformed text beginning with the managed marker prefix |
| schedule detail | mapping | compared without field coercion | non-mapping including `false`, `null`, empty string |
| schedule `task_params` | mapping | exact/type-strict existing comparison; no normalization | non-mapping |

The automatic create cap is `semaphore_reconcile_max_creates: 2` in role defaults. A caller may deliberately override that variable; the schedule create count and template read-set-derived create count are checked against the configured value, and each post-diff `new` count is asserted again before apply. This keeps the unattended default small while allowing an explicit reviewed bulk run.

## Changes

- Template filtering now validates identity/read-set rows and applies explicit, field-scoped canonicalization instead of truthiness fallback. Empty template responses for non-empty catalogs, invalid IDs, malformed marker-prefixed descriptions, duplicate marker identity, and over-cap creation report errors before template apply. Markerless rows are valid unmanaged/orphan candidates.
- Markerless rows with a name equal to a rendered catalog target fail closed as ambiguous (lost managed marker versus unmanaged duplicate), so reconcile cannot silently create a duplicate. Markerless rows with unrelated names, including the self-reference template, remain valid orphans.
- Markerless and unmarked descriptions are accepted as unmanaged rows; only malformed marker-prefixed descriptions fail. `arguments` and `survey_vars` share the table's false/null-to-empty equivalence.
- Template create cap is rechecked against the computed `semaphore_templates_diff.new` immediately after reconciliation and before either apply path.
- Schedule collection GET and its identity/schema/empty-response preflight now run before either resource type can be written. The combined template+schedule create count is checked against the cap at this same point. Schedule template-name resolution remains after template apply and uses the later fresh template GET, preserving R10.
- Schedule preflight validates observed row mappings, integer IDs, duplicate IDs, and names. Schedule comparison now rejects a non-mapping detail instead of replacing it with `{}`. A second schedule GET was removed; the early schedule collection is retained while only the required template list is refreshed after apply.
- Added local fixture tests for first/second reconcile, AC1a markerless orphan and lost-marker collision, AC5a's four equivalent arguments forms, survey falsy forms, malformed types, empty/partial identity data, duplicate identity, create cap, and malformed schedule detail.

## Verification

- `python3 scripts/tests/semaphore_schedules/run-tests.py`: 110 tests passed, including AC1a unmanaged orphan acceptance/lost-marker collision and AC5a `false`/`null`/`"[]"`/`[]` checks through both preflight and comparison.
- `python3 roles/semaphore_templates/tests/task_flow/run_task_flow_tests.py`: all seven local control-flow scenarios passed, including cross-resource preflight zero-write and external reserved-name rejection.
- All six changed task files under `roles/semaphore_templates/tasks/` were loaded with `yaml.safe_load`; the parsed `main.yml` structure was inspected to assert combined preflight precedes template apply and the schedule workflow remains a nested block.
- No real host, Semaphore API, deployment, or git write operation was used.

## Follow-up correction

Coordinator returned the initial implementation because schedule-side preflight ran after template apply. The read order was changed so both resource lists are checked and the combined create cap is enforced before the first write. R10 is preserved: schedule-to-template resolution remains after template apply against the refreshed template list. The task-flow marker scenario now verifies the cross-resource zero-write property locally.

The first correction report's `ansible-playbook --syntax-check` result was not a valid check of this role: the entry playbook loads it via dynamic `include_role`, which leaves the role task files unparsed. A subsequent YAML load found the indentation error in `main.yml`; it was fixed, and the task-file YAML load plus parsed block-structure assertions above are the validation for this correction.

## Follow-up correction: guard ordering and ambiguous marker loss

Moved `schedules_validate_config.yml` to immediately after name resolution, before any task registers/sets `semaphore_schedules_*` internal state. Its allowlist was not broadened: external predefinitions remain rejected. The task-flow fixture runs the same reserved-name guard before simulating internal read facts; existing external-pollution scenarios still fail at that guard, while legitimate later internal state no longer triggers it. Thus the change fixes ordering rather than weakening the guard.

For marker loss, a markerless row with a rendered name matching a catalog entry is now a preflight error. This covers both a lost marker and a hand-created duplicate, which cannot safely be distinguished. An unrelated markerless row remains an orphan. Tests exercise both cases and verify the would-be duplicate classification is blocked by preflight.

The review's mechanical duplicates were removed: one repeated `arguments`/`survey_vars == true` error loop and one repeated template create-cap assert (2 duplicate blocks removed). The boolean regression test now asserts exactly one error and its content. A diff sweep found no other exact duplicate blocks among this correction's edits. Schedule row-shape checks remain at two distinct phases intentionally: early no-write validation and later fresh-template resolution.

Row-shape checks remain at both the early cross-resource gate and the schedule-specific preflight: the former is the no-write boundary before template apply, while the latter also performs catalog/template resolution checks after the required fresh template GET. Keeping those phase-specific gates separate avoids moving R10 resolution earlier.

The similar schedule row-shape checks are intentionally duplicated across those two phase gates for the same reason: the first must block all writes, while the later check owns full schedule/template resolution against refreshed data. They are not normalization layers and have different inputs/timing.
