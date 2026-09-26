# Implementation: proxmox_patch_judgment_2a

## Result

- R1: `codex-classify.sh` now extracts policy section 4 and labels the prompt accordingly.
- R2/R3: dry-run derives major status from each reached node's `pve-manager`, `proxmox-ve`, and `base-files` versions. A missing or unparsable version is recorded as `版を判定できない` and stops automatic classification at `MAJOR_UPGRADE_DETECTED`; an AI-only major suggestion is appended to the notification without changing Status.
- R4: apply parses the re-dry-run `Inst` records for the same three packages and combines that result with the existing package-count threshold.
- R5: the healthcheck critical/warning evaluator is shared by `proxmox_healthcheck` and both apply post-healthcheck paths. This preserves the healthcheck role's existing result while adding its full critical set to apply.
- R6: the control-node check uses the execution host's `hostname -s` and exact VM-name matching. The obsolete `ansy` default was removed.

## Verification

- `ansible-playbook --syntax-check playbooks/proxmox_patch_dryrun.yml`
- `ansible-playbook --syntax-check playbooks/proxmox_patch_apply_node.yml`
- `ansible-playbook roles/proxmox_patch_dryrun/tests/test_major_versions.yml`: pve-manager/base-files major changes, same-major AI-only case, epoch versions, and invalid/missing version inputs agree between dry-run and apply fixtures.
- `ansible-playbook roles/proxmox_healthcheck/tests/test_shared_critical.yml`: normal input and quorum, ZFS collection/DEGRADED/FAULTED, apt, pveproxy, failed-unit, root-filesystem, and replication critical inputs.
- Existing blocked-remove fixture tests and `compare_dryrun_and_apply.sh` pass.
- `git diff --check` and `python3 scripts/check-doc-consistency.py` pass.

## Unconfirmed

- No real Proxmox host, Codex CLI, Slack notification, or control-node placement was invoked.
- The fixture coverage does not run the apply role's retry loop or its final notification path end-to-end; both initial and retry paths call the same shared evaluator, and their exit-code behavior remains unchanged by inspection.
