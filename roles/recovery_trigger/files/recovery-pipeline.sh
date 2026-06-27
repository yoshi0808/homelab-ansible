#!/bin/bash
# /usr/local/bin/recovery-pipeline.sh <target> <escalate_immediately>
#
# Autonomous recovery orchestrator. Runs as recovery-runner on quory.
# Called by recovery-trigger.sh via sudo.
#
# Recovery ladder (policy §8):
#   1. recovery_service_restart.yml  (authy/monnie only — not sophos-fw)
#   2. recovery_vm_reboot.yml        (all targets)
#   3. recovery_ha_failover.yml      (hacritical targets only — enforced by playbook)
#   All-fail → escalation notification
#
# Lock file is created by recovery-trigger.sh; removed by EXIT trap here.

set -euo pipefail

TARGET="${1:-}"
ESCALATE_IMMEDIATELY="${2:-0}"

LOCK_FILE="/var/run/homelab-recovery/${TARGET}.lock"
ANSIBLE_DIR=/home/yoshi/homelab-ansible
INVENTORY=inventories/homelab/hosts.yml
LOG_TAG="homelab-recovery-pipeline"

cleanup() {
  rmdir "$LOCK_FILE" 2>/dev/null || true
  logger -t "$LOG_TAG" "EXIT $TARGET: lock released"
}
trap cleanup EXIT

logger -t "$LOG_TAG" "START $TARGET (escalate_immediately=$ESCALATE_IMMEDIATELY)"

apb() {
  ansible-playbook -i "$INVENTORY" "$@"
}

cd "$ANSIBLE_DIR"

# ---------------------------------------------------------------------------
# Flapping guard: skip ladder, go straight to escalation
# ---------------------------------------------------------------------------
if [[ "$ESCALATE_IMMEDIATELY" == "1" ]]; then
  logger -t "$LOG_TAG" "ESCALATE $TARGET: flapping detected, skipping ladder"
  apb playbooks/recovery_escalate.yml \
    -e target="$TARGET" \
    -e "escalate_reason=直近24時間に3回以上の自律復旧が実行されました。フラッピングの可能性があります。手動調査が必要です。"
  exit 0
fi

# ---------------------------------------------------------------------------
# Trigger notification (best-effort — failure does not stop the pipeline)
# ---------------------------------------------------------------------------
apb playbooks/recovery_notify_trigger.yml \
  -e target="$TARGET" || true

# ---------------------------------------------------------------------------
# Ladder step 1: Service restart (not applicable to sophos-fw)
# §8: authy → freeradius, monnie → grafana/prometheus/loki/unpoller
# ---------------------------------------------------------------------------
overall=escalate

if [[ "$TARGET" != "sophos-fw" ]]; then
  logger -t "$LOG_TAG" "LADDER1 $TARGET: attempting service restart"
  if apb playbooks/recovery_service_restart.yml -e target="$TARGET"; then
    logger -t "$LOG_TAG" "LADDER1 $TARGET: service restart OK"
    overall=ok
  else
    logger -t "$LOG_TAG" "LADDER1 $TARGET: service restart FAILED, proceeding to ladder2"
  fi
fi

# ---------------------------------------------------------------------------
# Ladder step 2: VM reboot
# ---------------------------------------------------------------------------
if [[ "$overall" != "ok" ]]; then
  logger -t "$LOG_TAG" "LADDER2 $TARGET: attempting VM reboot"
  if apb playbooks/recovery_vm_reboot.yml -e target="$TARGET"; then
    logger -t "$LOG_TAG" "LADDER2 $TARGET: VM reboot OK"
    overall=ok
  else
    logger -t "$LOG_TAG" "LADDER2 $TARGET: VM reboot FAILED, proceeding to ladder3"
  fi
fi

# ---------------------------------------------------------------------------
# Ladder step 3: HA failover (playbook enforces hacritical tag check internally)
# ---------------------------------------------------------------------------
if [[ "$overall" != "ok" ]]; then
  logger -t "$LOG_TAG" "LADDER3 $TARGET: attempting HA failover"
  if apb playbooks/recovery_ha_failover.yml -e target="$TARGET"; then
    logger -t "$LOG_TAG" "LADDER3 $TARGET: HA failover OK"
    overall=ok
  else
    logger -t "$LOG_TAG" "LADDER3 $TARGET: HA failover FAILED (or not eligible)"
  fi
fi

# ---------------------------------------------------------------------------
# Final escalation if all ladder steps failed
# ---------------------------------------------------------------------------
if [[ "$overall" != "ok" ]]; then
  logger -t "$LOG_TAG" "ESCALATE $TARGET: all recovery attempts failed"
  apb playbooks/recovery_escalate.yml \
    -e target="$TARGET" \
    -e "escalate_reason=サービス restart・VM リブート・HA フェイルオーバーがすべて失敗しました。手動調査が必要です。"
fi

logger -t "$LOG_TAG" "DONE $TARGET: overall=$overall"
