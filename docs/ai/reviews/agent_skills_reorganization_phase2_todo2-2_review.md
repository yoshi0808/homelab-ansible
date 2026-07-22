# Review: Phase 2 TODO 2-2 System Context

Date: 2026-07-22

Reviewer: `reviewer` (Codex)

## Target

- `docs/ai/context/system/overview.md`
- `docs/ai/context/system/proxmox.md`
- `docs/ai/context/system/radius.md`
- `docs/ai/context/system/monitoring.md`
- `docs/ai/context/system/semaphore.md`
- `docs/ai/reviews/agent_skills_reorganization_phase2_todo2-2_implement.md`

Scope excluded the contents of `docs/ai/context/ansible/` and changes to any
playbook or role.

## Decision

**Commit candidate.** The five System Context files satisfy TODO 2-2 and contain no
must-fix factual or security issue.

- must-fix: 0
- suggestion: 2
- nit: 0

The suggestions below improve safety precision and make the files easier to consume
in TODO 2-4. Neither blocks this System Context set.

## Findings

### suggestion: Describe `proxmox_patch_dryrun.yml` as “no package apply” rather than broadly read-only

File: `docs/ai/context/system/proxmox.md:31`

The sentence groups `proxmox_patch_dryrun.yml` with health/hardware/snapshot checks as
“read-only診断”. The playbook is currently marked `safe-readonly`, and it does not
apply package upgrades, reboot, or migrate guests. However, its documented execution
includes `apt-get update`, in addition to script deployment and local report output.
That refreshes package metadata even though it does not install upgrades.

For safety precision, a future revision should distinguish this playbook as
“実patchなし（package metadata refresh and simulation only）” instead of implying
the same degree of read-only behavior as pure observation. This is a documentation
clarification; changing the playbook or its tester-gate classification is outside
this review.

### suggestion: Add a timing dimension to the intended-reader notes before TODO 2-4 integration

Files: all five System Context files, final `想定読者Role` line

The notes correctly match the initial TODO 2-4 depth model: Tech Lead reads the
overview deeply, while Implementer/Reviewer/Tester read the target System Context in
detail. They are therefore valid source material.

TODO 2-4 must also decide *when* each Role reads a Context (startup, task start,
on-demand, or not needed). The current notes encode depth but not timing, and use
`その他` rather than naming the Coordinator explicitly. Before direct conversion to
the final matrix, add or derive those two dimensions centrally in TODO 2-4. It is not
necessary to duplicate the full matrix into every System Context file.

## Factual cross-check

### Overview

- Inventory groups and hosts match `inventories/homelab/hosts.yml`:
  `dev_nodes/ansy`, `control_nodes/quory`, `semaphore_servers/ansy+quory`,
  `proxmox/pve1+pve2`, `radius_servers/authy`, and
  `monitoring_servers/monnie`.
- The development/Git/production-execution separation matches `docs/ai/core.md`.
- The text correctly avoids assuming current guest placement, schedule enablement,
  service state, or automatic failover between the two Semaphore environments.

### Proxmox

- The node order and rolling flow match `proxmox_patch_weekly_full.yml`: global
  healthcheck/dry-run, then pve2 evacuation/apply/post-check/restore, followed by the
  same sequence for pve1.
- The weekly preflight allows an external controller and rejects a Proxmox node or a
  controller hosted as a cluster guest; the default allowed controller is quory.
- The single-node apply role checks controller placement, running VM/CT evacuation,
  pre-healthcheck, and pre-apply simulation before destructive work.
- Healthcheck, hardware-check, snapshot classification, recovery mute targets, and
  one-line summary statements match the corresponding roles/playbooks.

### RADIUS

- Inventory has one RADIUS target, authy.
- The healthcheck observes FreeRADIUS service state, RADIUS listeners, journal,
  memory, and root filesystem, then classifies in Ansible and saves the report on the
  controller.
- Proxmox patch flows set recovery mute for authy.
- The text makes no unsupported redundancy or fixed guest-placement assumption and
  includes no credential value or credential storage detail.

### Monitoring

- Inventory has one monitoring target, monnie.
- Prometheus, Grafana, Loki, unpoller, listener, memory, and root-filesystem claims
  match the collector and Ansible classification.
- `cert_renew.yml` pauses monitoring before Grafana deployment/restart and resumes it
  afterwards; Proxmox patch flows set recovery mute for monnie.
- The Context correctly limits healthcheck coverage and does not claim end-to-end
  health for every exporter/dashboard/log source.

### Semaphore

- `semaphore_servers` contains ansy and quory; `control_nodes` contains quory.
- `roles/systemd_timers/defaults/main.yml` comments the listed healthcheck/dry-run
  timers as migrated to Semaphore UI, while retaining the quory certificate renewal
  timer. The Context correctly treats actual UI schedule state as external and
  currently unverifiable from Git.
- `cert_renew.yml` is `risk-accepted` and deploys certificates to ansy's Semaphore,
  Proxmox UIs, and Grafana, with temporary CA material cleanup.
- `cert_renew_quory.yml` runs from a systemd timer; under check mode its CA
  preparation/issuance/cleanup still run while Semaphore deployment/restart is
  gated. The safety warning accurately reflects that behavior.

## Security and sensitive-value audit

Across the five System Context files:

- IPv4/CIDR literal values: 0
- VLAN ID values: 0
- VM ID values: 0
- Password/token/shared-secret/private-key values: 0
- Webhook URLs or public-key material: 0

References to the categories `IPアドレス`, `VLAN ID`, `VM ID`, `password`, `token`,
and similar terms occur only as prohibitions. Host references are inventory names or
`.internal` FQDNs, consistent with `docs/ai/core.md`.

## Terminology and Role alignment

- `Coordinator`, `Tech Lead`, `Implementer`, `Reviewer`, and `Tester` usage is
  compatible with `docs/ai/core.md` and `docs/ai/role-routing-index.md`.
- The Context files treat current code/inventory/Policy as higher priority and do not
  infer authority from identity names.
- The intended-reader notes are consistent with the initial TODO 2-4 depth matrix,
  subject to the timing/Coordinator suggestion above.

## `docs/ai/context/ansible/` boundary

The target implementation lists only `docs/ai/context/system/` files and does not
reference or duplicate Ansible Repository Context content. This review did not read
or evaluate files under `docs/ai/context/ansible/`.

Both `docs/ai/context/system/` and `docs/ai/context/ansible/` are currently untracked
in the shared worktree. Git can confirm path separation, but cannot prove which live
agent authored an untracked file. Accordingly, “the implementer did not touch the
other team's files” is supported by the implementation record and separated target
paths, but authorship cannot be independently established from Git metadata until
the files have a tracked baseline.

## Verification performed

- Read all five System Context files and the implementation record.
- Compared inventory group/host mappings with
  `inventories/homelab/hosts.yml`.
- Compared factual claims with the named healthcheck, hardware, snapshot, patch,
  certificate-renewal, notification, and timer playbooks/roles.
- Searched the five files for IPv4/CIDR literals, numeric VLAN/VM identifiers,
  credential assignments, private-key markers, webhook URLs, and public-key
  material.
- Checked `git status`, target paths, and worktree scope without modifying code or
  `docs/ai/context/ansible/`.
- No runtime or external-system test was needed because this change is documentation
  only.

