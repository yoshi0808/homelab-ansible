# Fixtures for `scripts/check-doc-consistency.py`

`check-doc-consistency.py` reads file content from the **git index**
(`git show :<path>`), the same convention `scripts/check-staged-yaml.py`
uses — see the implement record
`docs/ai/reviews/norm_drift_mechanical_check/2026-08-01_003_implement.md`
§2.2 for why.

The fixtures below are **plain file trees with no `.git` of their own** —
they are tracked in this repository like any other file. Running
`check-doc-consistency.py --repo-root` directly against one of them will
fail with "not a git working tree" (by design: the script refuses to guess
at a non-git directory). To actually exercise a fixture, use
`run-fixture-checks.sh`, which copies each fixture into a throwaway temp
directory, runs `git init` + `git add -A` there (no commit — `git show
:<path>` and `git ls-files` both read the index directly), runs the checker
against that temp copy, and deletes it afterward:

```sh
scripts/tests/fixtures/run-fixture-checks.sh
```

This is the reproduction procedure for AC3 (`docs/ai/reviews/norm_drift_mechanical_check/2026-08-01_002_requirement.md`):
anyone who checks out this repository can run that one command and see,
for each fixture, which check fails and why.

## Fixtures

| Fixture | Exercises | Expected result |
| --- | --- | --- |
| `clean_baseline/` | Nothing broken | `exit 0`, all three checks OK |
| `check1_tester_gate_mismatch/` | AC3 / check1 | `exit 1`; `playbooks/sample.yml` says `safe-readonly`, `playbooks/README.md` says `risk-accepted` |
| `check2_model_effort_mismatch/` | AC3 / check2 | `exit 1`; `.claude/agents/sample.md` says `effort: high`, `docs/ai/roles/coordinator.md` says `medium` |
| `check3_broken_link/` | AC3 / check3 | `exit 1`; `docs/ai/note.md` links to a file that does not exist |
| `empty_playbooks/` | AC4 | `exit 2`; `playbooks/` has no `*.yml`, so check1's input set is empty and must error, not PASS |

`run-fixture-checks.sh` has this exact exit-code table built in and fails
loudly if any fixture's actual exit code stops matching it.

`clean_baseline/` and every mismatch fixture also carries one
`` `[example](...)` `` written inside an inline code span, mirroring the two
known false-positive shapes in the real repo (AC2). None of the fixtures'
expected output should ever mention it — if one does, `_strip_code_regions`
in `check-doc-consistency.py` regressed.

Each mismatch fixture is built so that **only the check under test fails**
— the other two checks' inputs are kept internally consistent — so the
output attributes the failure to exactly one check, per AC3 ("どの検査の
どの対象が不一致かが出力から判別できる").

## Editing a fixture

Just edit the files directly; there is no index to keep in sync since these
are plain trees, not git repos. `run-fixture-checks.sh` builds the
throwaway index fresh on every run.
