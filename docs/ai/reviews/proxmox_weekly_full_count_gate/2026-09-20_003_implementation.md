# Implementation: Proxmox weekly full count gate

## Result

- `apply_forecast.yml` now produces `_apply_forecast_apply_gate` on the same
  `run_once` source host as `_final_status`.  Its `evaluated`, `threshold`, and
  `blocking_nodes` fields implement the requirement's §5.1 contract.
- Step 2b validates that contract only after the existing proceed decision.  A
  missing or malformed fact fails closed; a nonempty `blocking_nodes` list sends
  one patches notification, sets `_weekly_full_skip`, and ends cleanly before
  the mute and all subsequent apply-path plays.
- The consumer does not read the apply defaults.  The producer remains the sole
  reader, and the existing apply-role default remains the only threshold value.
- The forecast notification wording is now neutral to Friday dry-run and
  Saturday chain contexts.

## Self-verification

- Direct producer fixture (`/tmp/proxmox-weekly-full-fixtures/producer.yml`,
  `--check`) passed with node counts 101, 100, and 99: only 101 entered
  `blocking_nodes`; `threshold` was integer `100`; `evaluated` was boolean
  `true`; the fact remained on the run-once source host.
- Consumer fixtures (`--check`) passed for an over-threshold node (clean skip
  and one suppressed `patches` notification containing node, count, and
  threshold) and an empty `blocking_nodes` list (no skip).  The notification
  send task was skipped by `skip_notifications` and check mode; no Slack was
  sent.  The fixture's notification-capture sub-include was intentionally
  unresolved under `/tmp` and rescued by existing best-effort handling; this
  did not affect the notification suppression assertion.
- Fail-closed fixtures produced nonzero exits for: missing fact, non-dict
  fact, `evaluated != true`, non-integer threshold, non-list blocking nodes,
  and each missing required blocking-node field.
- `ansible-playbook --syntax-check` passed for weekly full and dry-run.
  `git diff --check` passed.  Static checks confirmed one threshold declaration
  and no apply-defaults lookup in Step 2b.  Existing clean-skip/fail branches
  are unmodified by the diff.

## Unresolved

- No real host, Semaphore job, or Slack endpoint was used.  Tester acceptance
  remains required for the full AC suite and the actual chain's import path.
