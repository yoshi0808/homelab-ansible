#!/usr/bin/env python3
"""Task-layer control-flow test for the block/rescue/always shape used by
roles/semaphore_templates/tasks/main.yml's schedule reconcile (2026-08-09,
docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_019_review_
implementation_r2.md item 3). The filter suite (scripts/tests/
semaphore_schedules/, 92 tests) never executes this control flow -- it
calls the pure-Python filter functions directly, with no Ansible runtime
involved.

Drives fixture_pattern.yml, a **structural mirror** of tasks/main.yml's
schedule block/rescue/always (see that file's header comment for why a
mirror rather than a literal drive of the checked-in role).

**Important discovery made while building this test (recorded here and in
the implement record, not something this test tries to "fix"):**
ansible-core 2.20.1's `[ERROR]: Task failed: ...` console banner shows a
failing task's raw `msg` **even when that task has `no_log: true`** --
only the later `fatal: [...]: FAILED! => {...}` JSON dump is censored.
Verified with two minimal, no-rescue-involved probes: a bare
`ansible.builtin.fail` with `no_log: true`, and a genuinely-failing
`ansible.builtin.uri` with `no_log: true` -- both printed their `msg` raw
via `[ERROR]:` before any rescue could run. This is an ansible-core
characteristic, not a bug in this role's rescue chain, and it cannot be
fixed by any rescue-based scrub (the banner is emitted for the
*originating* task, before its rescue block even starts). It applies
equally to the pre-existing, unmodified template-side rescue in
tasks/main.yml -- nothing about the 2026-08-09 schedule-side changes
introduced or worsened it.

Separately (and confirmed empirically -- see the two probes above), none
of this role's actual `ansible.builtin.uri` tasks ever produce a failure
`msg` containing the Authorization header value or response body in the
first place ("Status code was N and not [...]: HTTP Error N: <reason>"
only) -- so this banner behavior is not currently exploitable through any
task that actually exists in this role. It is the "万一" (unlikely, just
in case) scenario the role's own header comments already describe.

Given this, what *is* controllable -- and what the 2026-08-09 re-review's
High #1 finding was actually about -- is everything downstream of the
originating task's own banner: the rescue's own re-raise, and the saved
report. This test asserts exactly that: the sentinel may appear (once) in
the originating task's own unavoidable banner, but must never appear
again afterward -- not in the rescue's handling, not in the final
re-raised failure, and never in the saved report JSON.

Scenario A (report dir writable): asserts the sentinel does not reappear
  anywhere in the console output *after* the point where the rescue takes
  over, and never appears in the saved report JSON; asserts the
  ***REDACTED-TOKEN*** marker is what actually reaches both.
Scenario B (report dir made unwritable by a real, local, non-root chmod on
  its parent -- not a simulated failure): asserts the run still fails
  non-zero and that BOTH the original failure and the report-save failure
  are visible in the output (a report-save failure must not silently
  replace the original one), with the same post-rescue sentinel-absence
  check.

Scenario C (2026-08-09, 3rd-round re-review docs/ai/reviews/
  semaphore_schedules_as_code/2026-08-09_020_review_implementation_r3.md
  Critical #1): the fixture genuinely fails (as in scenario A), but the
  run is invoked with `-e '{"fixture_run_failed": false}'` -- a **native**
  boolean false, which beats `set_fact` in Ansible's variable precedence
  and would silently defeat a naive `when: fixture_run_failed`. Asserts rc
  is still non-zero (the `ansible_failed_result is defined` fallback in
  the final re-raise task must catch this) and that the output still shows
  *some* indication of a failure, even though the flag-driven message text
  is necessarily degraded (this is the documented, accepted trade-off: the
  fix guarantees the failure is never silently absorbed, not that the
  displayed reason survives an adversarial override of the same name).

Scenario D (same review, Medium #2 still open after round 2): the report
  write is forced to go UNREACHABLE (not FAILED) via `ansible_remote_tmp`
  pointed at a directory this process cannot write into -- `rescue:` does
  not catch UNREACHABLE at all (verified empirically; see the module
  docstring in fixture_pattern.yml), so this exercises the
  `ignore_unreachable: true` + registered-result path instead. Asserts rc
  is still non-zero and that the *original* fixture failure's identifying
  text is still present in the output (not just the report-save failure).

Scenario E (2026-08-09, 4th-round re-review docs/ai/reviews/
  semaphore_schedules_as_code/2026-08-09_023_review_implementation_r4.md
  Critical #1): the residual gap scenario D's `ansible_failed_result is
  defined` fallback cannot close. Here the fixture *block itself succeeds*
  (`fixture_should_fail=false` -- unlike every other scenario, which always
  makes the block fail first), and *only* the report write goes
  UNREACHABLE. Since `ignore_unreachable` never triggers `rescue`,
  `ansible_failed_result` is never set at all in this run -- so if
  `-e '{"fixture_report_save_failed": false}'` (native false) is also
  supplied, the old final-task logic (flags OR `ansible_failed_result is
  defined`) would have all three disjuncts false and exit 0 despite the
  report never having been saved. This is exactly what the reserved-name
  guard at the top of fixture_pattern.yml exists to close: it rejects the
  pre-defined `fixture_report_save_failed` name *before* the block or the
  report write ever run, regardless of whether the block was going to
  succeed or fail. Asserts rc is non-zero and that the guard's own message
  (not a downstream one) is what's shown -- this scenario is expected to
  stop before the report write is even attempted.

Loopback/localhost only -- fixture_pattern.yml uses `hosts: localhost,
connection: local` and never calls a network API. No real host, no real
Semaphore API, no real IP is ever touched.

Usage: python3 run_task_flow_tests.py
"""
import json
import os
import stat
import subprocess
import sys
import tempfile

SENTINEL = "TASKFLOWTEST-SENTINEL-TOKEN-9f3a7c21"
# The rescue task's name in fixture_pattern.yml -- everything in the
# console output from this line onward is "post-rescue" and must never
# contain the raw sentinel again (only the originating task's own
# ansible-core banner, *before* this line, is allowed to show it raw --
# see the module docstring).
RESCUE_MARKER = "Build a token-scrubbed copy of the original failure"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
FIXTURE_PLAYBOOK = os.path.join(HERE, "fixture_pattern.yml")


def run_playbook(report_dir, extra_args=None):
    cmd = [
        "ansible-playbook", FIXTURE_PLAYBOOK,
        "-e", f"fixture_secret_token={SENTINEL}",
        "-e", f"fixture_report_dir={report_dir}",
    ]
    if extra_args:
        cmd += extra_args
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60,
    )
    return proc.returncode, proc.stdout


def post_rescue_output(output):
    """Everything from the rescue task onward -- the part this role's code
    actually controls and can be held to a "sentinel never appears" bar.
    Falls back to the full output if the marker is somehow missing (which
    would itself be worth flagging as a test-setup problem)."""
    idx = output.find(RESCUE_MARKER)
    return output[idx:] if idx >= 0 else output


def scenario_a(scratch):
    report_dir = os.path.join(scratch, "reports_a")
    os.makedirs(report_dir, exist_ok=True)

    rc, output = run_playbook(report_dir)
    problems = []

    if rc == 0:
        problems.append("scenario A: expected non-zero rc (the fixture always fails), got 0")
    if RESCUE_MARKER not in output:
        problems.append("scenario A: rescue marker task not found in output at all — cannot evaluate post-rescue leakage")
    if SENTINEL in post_rescue_output(output):
        problems.append("scenario A: sentinel (token) appeared *after* the rescue took over — scrub did not happen before the console re-raise")
    if "***REDACTED-TOKEN***" not in post_rescue_output(output):
        problems.append("scenario A: no ***REDACTED-TOKEN*** marker in the post-rescue output — scrub must redact the token, not delete the whole message")

    report_path = os.path.join(report_dir, "latest.json")
    if not os.path.exists(report_path):
        problems.append("scenario A: expected the report to be saved (always: must run even on failure) — latest.json not found")
    else:
        with open(report_path) as f:
            report_content = f.read()
        if SENTINEL in report_content:
            problems.append("scenario A: sentinel (token) appeared in the saved report JSON")
        report = json.loads(report_content)
        if report.get("failed") is not True:
            problems.append(f"scenario A: report 'failed' should be true, got {report.get('failed')!r}")
        if "***REDACTED-TOKEN***" not in (report.get("failed_msg") or ""):
            problems.append("scenario A: report 'failed_msg' shows no evidence of scrubbing")

    return problems


def scenario_b(scratch):
    # A real, local, non-destructive permission failure: make the parent of
    # the report dir non-writable by the current user, so the `copy` task
    # inside fixture_pattern.yml's always: block genuinely fails.
    unwritable_parent = os.path.join(scratch, "unwritable_reports")
    os.makedirs(unwritable_parent, exist_ok=True)
    report_dir = os.path.join(unwritable_parent, "reports_b")  # deliberately not created
    os.chmod(unwritable_parent, stat.S_IRUSR | stat.S_IXUSR)  # r-x, no write
    try:
        rc, output = run_playbook(report_dir)
        problems = []

        if rc == 0:
            problems.append("scenario B: expected non-zero rc, got 0")
        if SENTINEL in post_rescue_output(output):
            problems.append("scenario B: sentinel (token) appeared after the rescue took over")
        if "fixture task失敗" not in output:
            problems.append("scenario B: the original fixture failure text is missing from the output — a report-save failure must not replace it")
        if "さらにレポート保存も失敗しました" not in output:
            problems.append("scenario B: no evidence of the report-save failure itself in the output — both failures must be visible")

        return problems
    finally:
        os.chmod(unwritable_parent, stat.S_IRWXU)  # restore so cleanup can remove it


def scenario_c(scratch):
    # Critical #1 (r3): a native-`false` extra-var on the exact internal
    # flag name must not suppress the re-raise. `-e key=value` (bare form)
    # always produces a *string*; JSON-form extra-vars (`-e '{"key":
    # false}'`) is required to get an actual native boolean through --
    # that distinction is the whole point (a bare-string override would
    # already be "truthy" and this bug wouldn't need a special test).
    report_dir = os.path.join(scratch, "reports_c")
    os.makedirs(report_dir, exist_ok=True)

    rc, output = run_playbook(
        report_dir,
        extra_args=["-e", '{"fixture_run_failed": false}'],
    )
    problems = []

    if rc == 0:
        problems.append(
            "scenario C: expected non-zero rc even with fixture_run_failed forced to native "
            "false via extra-vars — the block genuinely failed and must not be absorbed into success"
        )
    if "failed=0" in output and "unreachable=0" in output:
        # A quick corroborating check on the recap line itself, in addition to rc.
        problems.append("scenario C: PLAY RECAP shows failed=0 — the failure was absorbed")

    return problems


def scenario_d(scratch):
    # Medium #2 (still open after round 2, r3): force the report *write*
    # itself to go UNREACHABLE (not FAILED) via an unwritable
    # ansible_remote_tmp. `rescue:` never sees UNREACHABLE at all — this is
    # a fundamentally different Ansible result state, verified empirically
    # (see fixture_pattern.yml's header comment) — so this scenario
    # specifically targets the ignore_unreachable + registered-result path,
    # not the ordinary rescue path scenario B already covers.
    report_dir = os.path.join(scratch, "reports_d")
    os.makedirs(report_dir, exist_ok=True)
    unwritable_tmp_parent = os.path.join(scratch, "unwritable_remote_tmp")
    os.makedirs(unwritable_tmp_parent, exist_ok=True)
    bad_remote_tmp = os.path.join(unwritable_tmp_parent, "sub")
    os.chmod(unwritable_tmp_parent, stat.S_IRUSR | stat.S_IXUSR)  # r-x, no write
    try:
        rc, output = run_playbook(
            report_dir,
            extra_args=["-e", f"fixture_bad_remote_tmp={bad_remote_tmp}"],
        )
        problems = []

        if rc == 0:
            problems.append("scenario D: expected non-zero rc when the report write goes UNREACHABLE, got 0")
        # ignore_unreachable: true is specifically designed to make the
        # recap count this as "ignored", not "unreachable" -- that's the
        # whole point (the play survives instead of dying). The genuine
        # UNREACHABLE! event is still visible verbatim in the console
        # output, which is what this checks instead.
        if "UNREACHABLE!" not in output:
            problems.append("scenario D: no 'UNREACHABLE!' event found in the output — the UNREACHABLE condition was not actually triggered by this test setup")
        if "ignored=1" not in output:
            problems.append("scenario D: PLAY RECAP does not show ignored=1 — ignore_unreachable did not take effect as expected")
        if "fixture task失敗" not in output:
            problems.append("scenario D: the original fixture failure text is missing from the output — an UNREACHABLE report-save must not erase it")

        return problems
    finally:
        os.chmod(unwritable_tmp_parent, stat.S_IRWXU)  # restore so cleanup can remove it


def scenario_e(scratch):
    # r4 Critical #1: schedule processing SUCCEEDS, only the report write
    # goes UNREACHABLE, and the report-save failure fact is pinned to
    # native false via extra-vars. Unlike scenario D, `fixture_should_fail`
    # is explicitly false here, so `ansible_failed_result` is *never* set
    # in this run at all (no rescue ever fires) -- the old three-disjunct
    # `when:` would all be false, and only the reserved-name guard added
    # for r4 catches this.
    report_dir = os.path.join(scratch, "reports_e")
    os.makedirs(report_dir, exist_ok=True)
    unwritable_tmp_parent = os.path.join(scratch, "unwritable_remote_tmp_e")
    os.makedirs(unwritable_tmp_parent, exist_ok=True)
    bad_remote_tmp = os.path.join(unwritable_tmp_parent, "sub")
    os.chmod(unwritable_tmp_parent, stat.S_IRUSR | stat.S_IXUSR)  # r-x, no write
    try:
        rc, output = run_playbook(
            report_dir,
            extra_args=[
                "-e", "fixture_should_fail=false",
                "-e", f"fixture_bad_remote_tmp={bad_remote_tmp}",
                "-e", '{"fixture_report_save_failed": false}',
            ],
        )
        problems = []

        if rc == 0:
            problems.append(
                "scenario E: expected non-zero rc when schedule processing succeeds but report-only "
                "UNREACHABLE + native-false report_save_failed are combined — the reserved-name guard "
                "must reject this before it can be exploited"
            )
        if "reserved (_)fixture_* names already defined" not in output:
            problems.append(
                "scenario E: the reserved-name guard's own failure message was not found — "
                "the attack may have been caught by some other, less robust path instead, or not at all"
            )
        if "fixture_report_save_failed" not in output:
            problems.append("scenario E: the guard's message did not name fixture_report_save_failed specifically")

        return problems
    finally:
        os.chmod(unwritable_tmp_parent, stat.S_IRWXU)  # restore so cleanup can remove it


def main():
    scratch = tempfile.mkdtemp(prefix="semaphore_templates_task_flow_")
    try:
        problems = []
        problems += scenario_a(scratch)
        problems += scenario_b(scratch)
        problems += scenario_c(scratch)
        problems += scenario_d(scratch)
        problems += scenario_e(scratch)

        if problems:
            print("FAILED:")
            for p in problems:
                print(" -", p)
            return 1
        print(
            "OK: all five scenarios passed (no post-rescue sentinel leak; report-save failure did "
            "not replace the original failure; native-false extra-var override did not suppress "
            "the re-raise; UNREACHABLE report-save did not erase the original failure; the "
            "reserved-name guard rejects pre-defined internal-state names before they can be exploited)"
        )
        return 0
    finally:
        import shutil
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
