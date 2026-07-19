# Loki content survey for Alloy Phase 3 alert design

Date: 2026-07-19  
Scope: read-only Loki survey on `monnie:3100`; no Loki, Grafana, Alloy, or Ansible configuration was changed.

## Method

All reportable queries use a fixed end time of `2026-07-19T03:42:04Z`, the time immediately before this survey began. This prevents the Ansible/curl survey commands themselves from entering journald, being ingested by Alloy, and contaminating the results. The comparison windows are:

- 24 hours: `2026-07-18T03:42:04Z` through `2026-07-19T03:42:04Z`
- 7 days: `2026-07-12T03:42:04Z` through `2026-07-19T03:42:04Z`

Signature queries also exclude historical Ansible invocation records matching `(?i)ansible-ansible.*invoked with`. Those records can contain the query text rather than an actual incident. Samples below mask remote addresses and process identifiers.

The 24-hour window is the best available steady-state baseline. The 7-day window crosses the Promtail-to-Alloy migration and maintenance activity, and contains legacy `system` streams and pre-migration message formatting. It is useful for discovering event types, but not as a direct current-rate baseline.

## Stream contract and label inventory

Loki was ready. The label names returned were `filename`, `host`, `job`, `level`, `service_name`, and `unit`.

| Window | `job` values | `level` values | Notable `host` values |
|---|---|---|---|
| 24h | `network-devices`, `pve-nodes`, `ubuntu-nodes`, `unifi` | `debug`, `error`, `info`, `warning` | `ansy`, `authy`, `monnie`, `pve1`, `pve2`, `quory`, UniFi/network devices |
| 7d | 24h values plus `sophos-fw` and legacy `system` | `debug`, `error`, `info`, `warning` | 24h values plus `sophos-fw` and additional network devices |

Findings against the expected contract:

- `sophos-fw` is absent in the last 24 hours but present in the 7-day history.
- A historical `system` job exists in the 7-day window but not the 24-hour window.
- All four expected levels occur when an explicit time window is queried, even though the default recent label-values response showed only `info` and `warning`.
- Most `network-devices` and `unifi` entries have no `level`. Their parser only sets a level when a recognized severity token appears near the start of the message. Level-only alert rules are therefore blind to much of this traffic.
- Current `pve-nodes`, `sophos-fw`, and `ubuntu-nodes` pipelines retain message-only output. Some 7-day records retain legacy prefixes such as `error <host> <timestamp>`, confirming that this window spans a pipeline transition.

## Volume baseline

### Last 24 hours

| Job | Level absent | Debug | Info | Warning | Error |
|---|---:|---:|---:|---:|---:|
| `network-devices` | 8,560 | 0 | 0 | 0 | 0 |
| `pve-nodes` | 0 | 0 | 40,571 | 7 | 2 |
| `ubuntu-nodes` | 166 | 48 | 18,408 | 99 | 0 |
| `unifi` | 135 | 0 | 0 | 0 | 0 |

No `sophos-fw` or legacy `system` stream was present in this window.

Warning/error distribution by host:

| Job / host | Warning | Error |
|---|---:|---:|
| `pve-nodes` / `pve1` | 1 | 0 |
| `pve-nodes` / `pve2` | 6 | 2 |
| `ubuntu-nodes` / `ansy` | 24 | 0 |
| `ubuntu-nodes` / `authy` | 24 | 0 |
| `ubuntu-nodes` / `monnie` | 29 | 0 |
| `ubuntu-nodes` / `quory` | 22 | 0 |

Current rates are 4.125 Ubuntu warnings/hour, 0.292 PVE warnings/hour, and 0.083 PVE errors/hour. A generic Ubuntu warning alert would be noisy.

### Last 7 days

| Job | Level absent | Debug | Info | Warning | Error |
|---|---:|---:|---:|---:|---:|
| `network-devices` | 71,196 | 0 | 0 | 0 | 0 |
| `pve-nodes` | 0 | 0 | 88,178 | 38 | 35 |
| `sophos-fw` | 0 | 0 | 1,890 | 0 | 0 |
| legacy `system` | 119,782 | 2 | 46,473 | 3,623 | 3,600 |
| `ubuntu-nodes` | 323 | 57 | 66,599 | 822 | 623 |
| `unifi` | 1,122 | 0 | 0 | 0 | 0 |

Warning/error distribution by host:

| Job / host | Warning | Error |
|---|---:|---:|
| `pve-nodes` / `pve1` | 21 | 21 |
| `pve-nodes` / `pve2` | 17 | 14 |
| legacy `system` / `monnie` | 3,623 | 3,600 |
| `ubuntu-nodes` / `ansy` | 360 | 303 |
| `ubuntu-nodes` / `authy` | 46 | 0 |
| `ubuntu-nodes` / `monnie` | 377 | 317 |
| `ubuntu-nodes` / `quory` | 39 | 3 |

The 7-day rates are 0.208 PVE errors/hour, 0.226 PVE warnings/hour, 3.71 Ubuntu errors/hour, and 4.89 Ubuntu warnings/hour. The legacy `system` rates of about 21.4 errors and 21.6 warnings per hour are dominated by old `agetty` failures and must not drive current thresholds.

## Content and noise survey

The 99 current Ubuntu warnings normalize to:

- 69 Canonical Livepatch messages: `Client information is recent, not refreshing.`
- 24 equivalent non-prefixed `Client information is recent, not refreshing.` messages
- 5 `unpoller.service` warnings about unset `DAEMON_OPTS`
- 1 kernel `kauditd_printk_skb: 183 callbacks suppressed`

The seven current PVE warnings normalize to five invalid PVE ticket authentication failures, one authentication-key rotation, and one kernel high-resolution timer latency warning. The two current PVE errors are invalid-credential events. Sanitized examples:

```text
pvedaemon[PID] authentication failure; rhost=::ffff:<IP> user=admin@pve msg=invalid credentials
pveproxy[PID] authentication failure: 401 permission denied - invalid PVE ticket
pvestatd[PID] auth key pair too old, rotating..
kernel hrtimer: interrupt took 6090 ns
```

Useful historical PVE samples include corosync quorum-device/heuristics loss, a peer with no active links, `lxcfs.service` exiting, SSH pre-auth termination during maintenance, and a QEMU replication bitmap already in use. Historical Ubuntu/legacy-system error volume is heavily inflated by repeated `agetty` messages such as `failed to get terminal attributes: Input/output error` and `could not get terminal name: -22`.

## Unhealthy-signature survey

The table reports fixed-window 7-day counts after removing Ansible invocation false positives.

| Signature family | Effective count | Interpretation |
|---|---:|---|
| Out of memory / OOM-kill / standalone OOM | 0 | Clean baseline; strong alert candidate |
| Segfault / call trace / kernel BUG / panic | 0 | Clean baseline; strong alert candidate |
| I/O error / read-only filesystem / no space | 0 | Clean baseline; strong alert candidate |
| ZFS degraded/faulted/unavailable style events | 0 | Clean baseline; strong alert candidate |
| Certificate/TLS expiry or failure | 0 | Raw count was 7, all Ansible-command text false positives |
| Authentication failure | 27 | Real events; 7 were on `pve2` in the last 24h |
| Failed to start | 2 | Historical `alloy.service` failures on `monnie`; none in 24h |
| `Failed with result` | 14 | 12 historical Alloy and 2 LXCFS events; none in 24h |
| Broad `corosync` | 50 | Includes normal membership/service messages; unsuitable directly |
| Broad `quorum` | 20 | Includes normal membership messages; unsuitable directly |
| Corosync adverse subset | 8 | Four per PVE host in 7d, none in 24h |

The adverse corosync subset is limited to `lost connection with heuristics worker`, `no active links`, or `waiting for quorum device`. This is materially cleaner than matching all corosync/quorum content.

Before the Ansible-invocation exclusion, `panic` had one match and certificate/TLS had seven. Inspection showed all were query text embedded in old Ansible logs, not incidents. Alert queries must include the same exclusion or an equivalent source constraint.

## Proposed alert candidates

| Candidate | Initial threshold | Noise controls and rationale |
|---|---|---|
| Kernel fatal: OOM, panic, BUG, segfault, call trace | Critical on 1 event in 5m | Zero effective matches in 7d. Exclude Ansible invocation text. Split OOM from kernel-crash rules for routing clarity. |
| Storage fatal: I/O error, read-only filesystem, no space, ZFS bad state | Critical on 1 event in 5m; optionally require 2 in 10m for broad `I/O error` | Zero effective matches in 7d. Prefer precise device/ZFS phrases to avoid application-level text. |
| PVE corosync adverse state | Warning on 1 in 5m; critical on 2 in 10m or persistence | Zero in 24h; eight in 7d around restart/patch activity. Suppress during planned maintenance. PVE is investigate-only, so this adds useful detection without competing with an automated repair. |
| Service failed to start / failed result | Warning on 1 in 5m; critical if repeated or still failed after 10m | Zero in 24h, 16 historical events. Correlate with service state and maintenance. `monnie` Alloy failures can duplicate recovery Slack notifications. |
| Authentication failure burst | Warning at 5 in 5m per host/source/user; critical at 10 in 10m | Do not alert on a single event: 27 occurred in 7d and seven on `pve2` in 24h. Keep all events collected; suppress known-benign source patterns only in the alert expression. |
| PVE generic error fallback | Warning at 3 in 5m after excluding authentication failures and known maintenance text | Avoids paging for the current two isolated invalid-credential errors. Specific rules remain preferable. |
| Ubuntu error fallback | Warning at 3 in 10m after excluding known legacy `agetty` patterns | Current count is zero, but the 7d migration window shows that a raw `level=error` alert can become extremely noisy. |
| Ubuntu warning fallback | Do not alert on raw warning level; after exclusions, use 3 in 10m | Exclude known Livepatch “recent, not refreshing” and accepted `DAEMON_OPTS` noise. Those account for 98 of 99 current warnings. Prefer signature-specific rules. |
| Certificate/TLS failure or imminent expiry | Warning on 1 in 15m | Zero effective matches in 7d. Deduplicate against certificate-renewal/update Slack notifications. |
| Network/UniFi content failures | Signature-specific, independent of `level` | Most records lack a level. Start with explicit link/auth/device failure phrases; parser improvement can be a separate future change. |

## Duplication and recovery boundaries

- Autonomous recovery already covers `authy`, `monnie`, and `sophos-fw`; on `monnie` it can restart Prometheus, Grafana, Loki, and Unpoller. Alerts for these failures should correlate with recovery status and avoid sending a second notification for the same episode.
- Loki stream-absence alerts for `sophos-fw`, UniFi, or network devices risk duplicating existing recovery pull/push detection. Keep them low priority or omit them until recovery-notification correlation exists.
- `monnie` Alloy service-start failures overlap the recovery pipeline and its Slack path. A durable-failure alert is more useful than immediate duplicate paging.
- Certificate alerts may overlap certificate renewal/update notifications.
- PVE has investigation workflows but no automated recovery action wrapper. Clean PVE corosync and persistent service-failure alerts therefore provide relatively high incremental value.

## Recommended Phase 3 starting set

Start with the zero-baseline fatal families, the narrow PVE corosync adverse subset, persistent service failure, and burst-based authentication detection. Do not enable raw warning/error alerts without the exclusions above. Implement explicit self-contamination protection in every content-signature expression, and treat the 24-hour window as the current baseline until several post-migration days are available.

