#!/bin/bash
# quory-post-upgrade-check.sh
#
# Ansible-external (not deployed/managed by this repo's Ansible automation —
# requirement §9/§11). Runs at boot via quory-post-upgrade-check.service.
# Read-only: checks corosync-qdevice / chrony sync / Semaphore, notifies
# Slack, then removes the flag file. Does not change any configuration.
#
# Only acts if the flag file exists (i.e. the last reboot was caused by
# ubuntu_vm_full_upgrade's apply, not some other reboot) — see
# roles/ubuntu_vm_full_upgrade/tasks/reboot_quory.yml, which creates the flag
# file right before scheduling the delayed reboot.
#
# Manual placement (Ansible deployment automation is out of scope this round
# — requirement §9/§10):
#   1. Copy this file to /usr/local/sbin/quory-post-upgrade-check.sh on
#      quory, root:root, mode 0750.
#   2. Copy quory-post-upgrade-check.service to
#      /etc/systemd/system/quory-post-upgrade-check.service, then:
#        systemctl daemon-reload
#        systemctl enable quory-post-upgrade-check.service
#   3. Create /etc/ubuntu-vm-full-upgrade/slack-webhook-quory.conf (root:root,
#      mode 0600) containing exactly one line:
#        SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
#      (same webhook used for the #info channel — see
#      inventories/vars/slack.yml's slack_webhook_info, decrypted once and
#      copied here; this script cannot read Ansible Vault at boot time since
#      no Ansible process is involved — see implement.md §12 rationale, and
#      the same "quory-local file, mode 0600, not git-managed" pattern
#      already used for the cert_renew intermediate CA key,
#      docs/ai/prompts/cert_renew_policy.md §4.4).

set -uo pipefail

FLAG_FILE="/var/lib/ubuntu-vm-full-upgrade/quory-reboot-pending.flag"
WEBHOOK_CONF="/etc/ubuntu-vm-full-upgrade/slack-webhook-quory.conf"

# No-op unless this reboot was caused by ubuntu_vm_full_upgrade's apply.
[ -f "$FLAG_FILE" ] || exit 0

if [ -r "$WEBHOOK_CONF" ]; then
  # shellcheck source=/dev/null
  source "$WEBHOOK_CONF"
fi

# ---------------------------------------------------------------------------
# Checks (read-only). `After=network-online.target` in the .service only
# guarantees network reachability at unit start, not that corosync-qdevice
# or Semaphore have finished starting yet (both are also started around
# boot and can race this unit) — a single `systemctl is-active` right after
# boot can catch them mid-"activating" and falsely report CRITICAL
# (2026-07-11 review). wait_for_active polls with a bounded retry+interval
# instead of checking once or sleeping blindly.
#
# Ordering (2026-07-11 review): corosync-qdevice is checked AFTER chrony,
# not before. Checking it first (as an earlier version of this script did)
# freezes its value at ~10s into boot and never re-evaluates it — if qdevice
# only finishes starting at, say, 15s, the stale "inactive" reading from the
# first check would wrongly report CRITICAL even though it's fine by the
# time this script actually finishes. Placing it after chrony's up-to-50s
# wait gives it the same "more elapsed boot time before we give up" benefit
# semaphore's check already had.
#
# Timeout budget (must fit inside the .service's TimeoutStartSec=120):
#   chrony waitsync :  <= 10 tries x 5s = 50s  (chronyc's own retry/timeout)
#   corosync-qdevice: <= 3 tries x 5s  = 15s (2 sleeps between 3 tries)
#   semaphore       : <= 3 tries x 5s  = 15s (2 sleeps between 3 tries)
#   curl (Slack)    : <= 10s
#   worst-case total: ~90s, leaving a margin under 120s for process
#   startup/JSON build/misc overhead.
# ---------------------------------------------------------------------------

wait_for_active() {
  # wait_for_active <unit> <max_tries> <interval_seconds>
  # Polls `systemctl is-active <unit>` up to <max_tries> times, sleeping
  # <interval_seconds> between attempts. Prints the last observed status and
  # returns 0 if it became "active", 1 otherwise.
  local unit="$1" max_tries="$2" interval="$3" i status
  for ((i = 1; i <= max_tries; i++)); do
    status=$(systemctl is-active "$unit" 2>/dev/null) || status="inactive"
    if [ "$status" = "active" ]; then
      echo "$status"
      return 0
    fi
    [ "$i" -lt "$max_tries" ] && sleep "$interval"
  done
  echo "$status"
  return 1
}

# chronyc waitsync <max-tries> <max-correction> <max-skew> <interval>
# polls internally with retry+timeout and exits 0 once synced, 1 on timeout —
# no fixed sleep needed (requirement §7.2 explicitly asks for this).
if chronyc waitsync 10 0.5 0 5 >/tmp/quory-post-upgrade-chrony.$$  2>&1; then
  chrony_status="synced"
else
  chrony_status="not_synced"
fi
chrony_detail=$(tail -1 /tmp/quory-post-upgrade-chrony.$$ 2>/dev/null)
rm -f /tmp/quory-post-upgrade-chrony.$$

qdevice_status=$(wait_for_active corosync-qdevice 3 5) || true
semaphore_status=$(wait_for_active semaphore 3 5) || true

criticals=()
[ "$qdevice_status" = "active" ] || criticals+=("corosync-qdevice is not active: ${qdevice_status}")
[ "$chrony_status" = "synced" ] || criticals+=("chrony did not sync in time: ${chrony_detail:-no detail}")
[ "$semaphore_status" = "active" ] || criticals+=("semaphore service is not active: ${semaphore_status}")

if [ "${#criticals[@]}" -eq 0 ]; then
  overall="OK"
  color="good"
else
  overall="CRITICAL"
  color="danger"
fi

criticals_text="(none)"
if [ "${#criticals[@]}" -gt 0 ]; then
  criticals_text=$(printf -- '- %s\n' "${criticals[@]}")
fi

body=$(cat <<EOF
Host: quory
Result: ${overall}
Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)

corosync-qdevice: ${qdevice_status}
chrony          : ${chrony_status} (${chrony_detail:-no detail})
semaphore       : ${semaphore_status}

Criticals:
${criticals_text}
EOF
)

# ---------------------------------------------------------------------------
# Notify (best-effort — do not let a Slack failure prevent flag cleanup)
# ---------------------------------------------------------------------------
if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
  payload=$(python3 -c '
import json, sys
print(json.dumps({
    "attachments": [{
        "title": "[quory-post-upgrade-check] " + sys.argv[1],
        "text": sys.argv[2],
        "color": sys.argv[3],
        "fallback": "[quory-post-upgrade-check] " + sys.argv[1],
    }]
}))
' "$overall" "$body" "$color")
  curl -fsS --max-time 10 -X POST -H 'Content-type: application/json' \
    --data "$payload" "$SLACK_WEBHOOK_URL" >/dev/null 2>&1 || true
fi

rm -f "$FLAG_FILE"
exit 0
