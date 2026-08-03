#!/bin/bash
# recovery-investigate-dispatch-quory.sh — deployed on quory
# Called via SSH forced command from dev-investigate@quory (R13c, Claude
# Code's read-only investigation key). This script is the sole authorization
# boundary (I-7 in the catalog below) — dev-investigate has no sudo and no
# other entry point, so nothing upstream of this script is a security
# control.
#
# Contract source: docs/ai/reviews/dev_prod_boundary/2026-08-03_008_phase3_check_catalog.md
# §1 (class Q, 20 checks: Q1-Q4 bundle/investigation, Q5-Q7 reports, Q-C
# common system (8), Q8-Q12 quory-specific) plus §6 (D6, 4 checks: X1
# acl-status is Q-only; X2/X3/X4 users/unit-files/forced-command-keys are
# shared with classes G/P) — 24 total. Do not add checks beyond those
# tables without Yoshinobu's approval.
#
# All checks are read-only (I-1): no pvesh create/set/delete, no systemctl
# start/stop/restart/enable, no qm start/stop, no redirection, no tee/rm/mv/cp.
# SSH_ORIGINAL_COMMAND is never eval'd or otherwise shell-reinterpreted (I-2,
# same AR-048/AR-088 discipline as recovery-investigate-dispatch.sh). Checks
# that read a specific file resolve it through a fixed name/enum table here,
# or hand the raw (already-validated) operand to a helper that re-validates
# and holds its own fixed BASE (incident-bundle-helper /
# recovery-reports-helper) — this script never concatenates operand text
# into a path itself (I-3).
set -euo pipefail

cmd="${SSH_ORIGINAL_COMMAND:-}"

if [[ "$cmd" == *$'\n'* || "$cmd" == *$'\r'* ]]; then
  echo "denied: command contains a line break" >&2
  exit 1
fi

# Fixed arity: at most 3 declared operands anywhere in the table below
# (report-show's playbook/target/file form is the widest). `read` captures
# any 4th+ token into `extra`, so it is rejected before dispatch (I-4).
read -r check p1 p2 p3 extra <<<"$cmd"
if [[ -n "$extra" ]]; then
  echo "denied: too many parameters for '${check:-unknown}'" >&2
  exit 1
fi

deny_count() {
  echo "denied: invalid parameter count for '$check'" >&2
  exit 1
}

deny_invalid() {
  local param_name="$1"
  echo "denied: invalid ${param_name} for ${check}" >&2
  exit 1
}

# --- Shared validation constants (kept identical to the helpers they front,
# so a rejection here and a rejection inside the helper agree) ---
BUNDLE_ID_RE='^semaphore-[0-9]{1,9}$'
NAME_RE='^[a-zA-Z0-9_-]+$'
# See recovery-reports-helper's own comment: '+' is needed for JST timestamp
# names (20260803_053711+0900.json); '.' is deliberately NOT added so ".."
# stays structurally unspellable.
FILE_RE='^[a-zA-Z0-9_+-]+\.json$'

# unit enum shared by status / journal-unit / unit-cat / deployed-hash's own
# self-entry. Fixed list only — never taken from an operand.
_is_valid_unit() {
  # An array + loop, not a multi-line `case` pattern: a `case` pattern list
  # split across lines with backslash-newline keeps each continued line's
  # leading whitespace as a literal character in the pattern (case patterns
  # are not word-split the way a `for ... in` list is), which would make
  # every entry after the first line silently unmatchable. See the implement
  # record for this file.
  local u="$1" valid
  local units=(
    recovery-probe.service
    recovery-probe-sandbox.service
    recovery-io.service
    homelab-incident-capture.service
    homelab-incident-capture.timer
    homelab-incident-investigate.service
    homelab-incident-investigate.timer
    semaphore.service
    ansible-cert-renew-quory.service
    ansible-cert-renew-quory.timer
    worktree-sync.service
    worktree-sync.timer
    ansible-authy-healthcheck.timer
    ansible-monitoring-healthcheck.timer
    ansible-proxmox-healthcheck.timer
    ansible-proxmox-hw-check.timer
    ansible-proxmox-patch-dryrun.timer
  )
  for valid in "${units[@]}"; do
    [[ "$u" == "$valid" ]] && return 0
  done
  return 1
}

case "$check" in
  # --- Q-A: failure bundle reference (R14c) — delegates to
  # incident-bundle-helper, which holds its own fixed BASE and re-validates
  # independently (defense in depth; this dispatch does not trust its own
  # validation alone). bundle-grep is intentionally NOT present — excluded
  # from the initial release per the catalog. ---
  bundle-list)
    [[ -z "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    exec /usr/local/sbin/incident-bundle-helper list-bundles
    ;;
  bundle-show)
    [[ -n "$p1" && -n "$p2" && -z "$p3" ]] || deny_count
    [[ "$p1" =~ $BUNDLE_ID_RE ]] || deny_invalid id
    case "$p2" in
      summary.json|semaphore-log.log|semaphore-hosts.log|semaphore-errors.log) ;;
      *) deny_invalid file ;;
    esac
    exec /usr/local/sbin/incident-bundle-helper show-bundle "$p1" "$p2"
    ;;
  investigation-list)
    [[ -z "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    exec /usr/local/sbin/incident-bundle-helper list-investigations
    ;;
  investigation-show)
    [[ -n "$p1" && -n "$p2" && -z "$p3" ]] || deny_count
    [[ "$p1" =~ $BUNDLE_ID_RE ]] || deny_invalid id
    case "$p2" in
      md|json) ;;
      *) deny_invalid ext ;;
    esac
    exec /usr/local/sbin/incident-bundle-helper show-investigation "$p1" "$p2"
    ;;

  # --- Q-B: reports/ reference (R13b + deployed-artifact hashes) —
  # delegates to recovery-reports-helper, same defense-in-depth rationale as
  # above. ---
  report-playbooks)
    [[ -z "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    exec /usr/local/sbin/recovery-reports-helper list-playbooks
    ;;
  report-list)
    case "$p2" in
      '')
        [[ -n "$p1" && -z "$p3" ]] || deny_count
        [[ "$p1" =~ $NAME_RE ]] || deny_invalid playbook
        exec /usr/local/sbin/recovery-reports-helper list-reports "$p1"
        ;;
      *)
        [[ -n "$p1" && -n "$p2" && -z "$p3" ]] || deny_count
        [[ "$p1" =~ $NAME_RE ]] || deny_invalid playbook
        [[ "$p2" =~ $NAME_RE ]] || deny_invalid target
        exec /usr/local/sbin/recovery-reports-helper list-reports "$p1" "$p2"
        ;;
    esac
    ;;
  report-show)
    case "$p3" in
      '')
        [[ -n "$p1" && -n "$p2" ]] || deny_count
        [[ "$p1" =~ $NAME_RE ]] || deny_invalid playbook
        [[ "$p2" =~ $FILE_RE ]] || deny_invalid filename
        exec /usr/local/sbin/recovery-reports-helper show-report "$p1" "$p2"
        ;;
      *)
        [[ -n "$p1" && -n "$p2" && -n "$p3" ]] || deny_count
        [[ "$p1" =~ $NAME_RE ]] || deny_invalid playbook
        [[ "$p2" =~ $NAME_RE ]] || deny_invalid target
        [[ "$p3" =~ $FILE_RE ]] || deny_invalid filename
        exec /usr/local/sbin/recovery-reports-helper show-report "$p1" "$p2" "$p3"
        ;;
    esac
    ;;

  # --- Q-C: common system checks (8) — verbatim from
  # recovery-investigate-dispatch.sh.j2, unchanged content (R11: same
  # vocabulary across classes). Only the operand-count guard differs, since
  # this dispatch parses all commands through one fixed-arity `read` (I-4)
  # instead of matching the literal string per check. ---
  failed)
    [[ -z "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    systemctl --failed --no-pager
    ;;
  disk)
    [[ -z "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    df -h
    ;;
  memory)
    [[ -z "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    free -h
    echo "--- OOM (last 20 kernel messages) ---"
    journalctl -k -n 20 --no-pager | grep -i 'oom\|out of memory' || echo 'no OOM entries'
    ;;
  load)
    [[ -z "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    uptime
    ;;
  network)
    [[ -z "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    ip addr
    echo "---"
    ip route
    echo "---"
    resolvectl status 2>/dev/null || cat /etc/resolv.conf
    ;;
  ports)
    [[ -z "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    ss -ltnup
    ;;
  journal-system)
    [[ -z "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    journalctl -p warning..err -n 50 --no-pager
    ;;
  dmesg)
    [[ -z "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    # journalctl -k reads the kernel ring buffer via journald, which
    # dev-investigate can read as a member of the systemd-journal group (no
    # sudo, no CAP_SYSLOG needed) — same rationale as
    # recovery-investigate-dispatch.sh.j2's dmesg arm.
    journalctl -k -n 50 --no-pager
    ;;

  # --- Q-D: quory-specific (5) ---
  status)
    [[ -z "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    # Fixed list: the first 8 of the unit enum (recovery pipeline +
    # Semaphore). Never built from an operand.
    for unit in recovery-probe.service recovery-probe-sandbox.service recovery-io.service \
      homelab-incident-capture.service homelab-incident-capture.timer \
      homelab-incident-investigate.service homelab-incident-investigate.timer \
      semaphore.service; do
      echo "=== ${unit} ==="
      systemctl status "${unit}" --no-pager -l || true
    done
    ;;
  journal-unit)
    [[ -n "$p1" && -n "$p2" && -z "$p3" ]] || deny_count
    _is_valid_unit "$p1" || deny_invalid unit
    case "$p2" in
      30m) since_value="-30 min" ;;
      1h) since_value="-1 hours" ;;
      2h) since_value="-2 hours" ;;
      6h) since_value="-6 hours" ;;
      12h) since_value="-12 hours" ;;
      24h) since_value="-24 hours" ;;
      *) deny_invalid window ;;
    esac
    journalctl -u "$p1" --since "$since_value" -n 300 --no-pager
    ;;
  # --- journal-ssh (catalog §7, D7, 2026-08-03) ---
  # Deliberately NOT an entry in the unit enum above. Three reasons:
  #   1. `sshd.service` on this host is an *alias*; the real unit is
  #      `ssh.service`. Asking for "sshd" and getting nothing back would look
  #      like "no SSH problems" when it means "wrong unit name".
  #   2. `ssh.socket` is enabled here, so per-connection sessions are logged
  #      under `sshd@<N>.service` instances, not under `ssh.service`. Querying
  #      only one of the three returns an empty result that proves nothing —
  #      the same trap `journal-system -p warning..err` already fell into.
  #   3. The unit enum is shared with `unit-cat`, and `systemctl cat 'sshd@*'`
  #      is not a thing. A glob cannot live in that enum.
  # All three unit selectors are literals in this file; the only operand is
  # the window, validated against the same fixed enum as journal-unit.
  journal-ssh)
    [[ -n "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    case "$p1" in
      30m) since_value="-30 min" ;;
      1h) since_value="-1 hours" ;;
      2h) since_value="-2 hours" ;;
      6h) since_value="-6 hours" ;;
      12h) since_value="-12 hours" ;;
      24h) since_value="-24 hours" ;;
      *) deny_invalid window ;;
    esac
    journalctl -u ssh.service -u ssh.socket -u 'sshd@*' \
      --since "$since_value" -n 300 --no-pager
    ;;
  unit-cat)
    [[ -n "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    _is_valid_unit "$p1" || deny_invalid unit
    systemctl cat "$p1"
    ;;
  semaphore-query)
    [[ -n "$p1" && -n "$p2" && -z "$p3" ]] || deny_count
    case "$p1" in
      recent-failed|running|task-errors|task-hosts|task-output|task-time|template-list) ;;
      *) deny_invalid query ;;
    esac
    [[ "$p2" =~ ^[0-9]+$ ]] || deny_invalid n
    exec /usr/local/bin/homelab-semaphore-query "$p1" "$p2"
    ;;
  deployed-hash)
    [[ -n "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    case "$p1" in
      recovery-probe) target_path=/usr/local/sbin/recovery-probe.py ;;
      incident-capture-collector) target_path=/usr/local/sbin/incident-capture-collector.py ;;
      incident-investigate) target_path=/usr/local/sbin/incident-investigate.py ;;
      recovery-push-dispatch) target_path=/usr/local/sbin/recovery-push-dispatch.sh ;;
      reports-helper) target_path=/usr/local/sbin/recovery-reports-helper ;;
      bundle-helper) target_path=/usr/local/sbin/incident-bundle-helper ;;
      semaphore-query) target_path=/usr/local/bin/homelab-semaphore-query ;;
      # Added 2026-08-03 (catalog §7). The timer's liveness is covered by the
      # daily drift check, but the script's *contents* are template-derived
      # and have no repo-side expected value (Tier 2) — this hash is the only
      # way to tell "the deployed copy changed" from "it did not".
      worktree-sync) target_path=/usr/local/sbin/worktree-sync.sh ;;
      investigate-dispatch-quory) target_path=/usr/local/sbin/recovery-investigate-dispatch-quory.sh ;;
      *) deny_invalid name ;;
    esac
    sha256sum -- "$target_path"
    ;;

  # --- §6 additions (D6, 2026-08-03): X1 is Q-only; X2-X4 are the same
  # contract on classes G/P (recovery-investigate-dispatch.sh.j2 /
  # recovery-investigate-dispatch-pve.sh.j2). No new write vocabulary here —
  # only getfacl / getent / systemctl list-unit-files / this identity's own
  # authorized_keys, all read. ---
  acl-status)
    [[ -n "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    # Fixed name->path table, never built from the operand (I-3). Reading a
    # path's ACL only requires traverse (x) on its parents, not any
    # permission on the path itself (verified locally: getfacl on a 0700
    # directory succeeds for another user who can only reach its parent) —
    # so this works under the same traverse-only grants Q1-Q7/Q11 already
    # rely on, with no sudo.
    case "$p1" in
      yoshi-home) target_path=/home/yoshi ;;
      semaphore-dir) target_path=/var/lib/semaphore ;;
      semaphore-db) target_path=/var/lib/semaphore/semaphore.db ;;
      reports-root) target_path=/home/yoshi/homelab-ansible/reports ;;
      *) deny_invalid path ;;
    esac
    getfacl -p -- "$target_path"
    ;;
  users)
    [[ -z "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    # uid bounds are fixed script constants (catalog §6.2 X2) — there is no
    # operand to take them from. /etc/shadow is never touched.
    while IFS=: read -r u_name _ u_uid _ _ _ u_shell; do
      if (( u_uid >= 1000 && u_uid <= 64999 )); then
        echo "${u_name}:${u_uid}:${u_shell}"
      fi
    done < <(getent passwd)
    ;;
  unit-files)
    [[ -z "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    systemctl list-unit-files --no-pager
    ;;
  forced-command-keys)
    [[ -z "$p1" && -z "$p2" && -z "$p3" ]] || deny_count
    # Self only: dev-investigate's own authorized_keys (catalog §6.2 X4 —
    # never another identity's file). Key material (key type + base64 blob)
    # is never printed, only the forced command path and comment field.
    entry_count=0
    while IFS= read -r keyline; do
      [[ -z "$keyline" || "$keyline" == \#* ]] && continue
      entry_count=$((entry_count + 1))
      read -r opts _ _ comment <<<"$keyline"
      if [[ "$opts" =~ command=\"([^\"]*)\" ]]; then
        cmd_path="${BASH_REMATCH[1]}"
      else
        cmd_path="(none)"
      fi
      echo "${entry_count}: command=${cmd_path} comment=${comment:-(none)}"
    done < /home/dev-investigate/.ssh/authorized_keys
    echo "total: ${entry_count} entries"
    ;;

  *)
    echo "denied: unknown command '${check:-}'" >&2
    exit 1
    ;;
esac
