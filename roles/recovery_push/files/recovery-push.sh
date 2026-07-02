#!/usr/bin/env bash
# recovery-push.sh: Notify quory of OnFailure event via SSH forced command.
# Called by recovery-trigger@.service as a oneshot.
# -F /dev/null: skip system ssh_config (bwrap UID mapping breaks ownership checks).
set -euo pipefail

KEY=/etc/homelab-recovery/push-key
KNOWN=/etc/homelab-recovery/push-known_hosts

exec ssh -T \
    -F /dev/null \
    -i "$KEY" \
    -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile="$KNOWN" \
    -o ConnectTimeout=15 \
    -o BatchMode=yes \
    "recovery-exec@quory.internal"
