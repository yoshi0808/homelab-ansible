#!/bin/bash
# proxmox-patch-apply-collect.sh
# Post-apply reboot requirement check. Returns JSON.
# Shell responsibility: collection and reboot_required determination only. No side effects.

set -uo pipefail

reboot_required="false"
reboot_trigger="none"

# Check 1: /var/run/reboot-required
if [ -f /var/run/reboot-required ]; then
  reboot_required="true"
  reboot_trigger="reboot-required-file"
fi

# Check 2: Compare running kernel vs installed proxmox-kernel packages.
# /var/run/reboot-required is not always created after a kernel update,
# so this comparison catches cases that the file-based check misses.
if [ "$reboot_required" = "false" ]; then
  running_ver=$(uname -r | sed 's/-pve//')
  for pkg in proxmox-kernel-6.17 proxmox-kernel-7.0; do
    installed_ver=$(dpkg-query -W -f='${Version}' "$pkg" 2>/dev/null)
    if [ -n "${installed_ver:-}" ]; then
      if dpkg --compare-versions "$installed_ver" gt "$running_ver"; then
        reboot_required="true"
        reboot_trigger="kernel-version-mismatch:${pkg} installed=${installed_ver} running=${running_ver}"
        break
      fi
    fi
  done
fi

running_kernel=$(uname -r)

REBOOT_REQUIRED="$reboot_required" \
REBOOT_TRIGGER="$reboot_trigger" \
RUNNING_KERNEL="$running_kernel" \
python3 - << 'PYEOF'
import json, os
from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=9))

print(json.dumps({
    "collected_at": datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S%z"),
    "reboot_required": os.environ["REBOOT_REQUIRED"] == "true",
    "reboot_trigger": os.environ["REBOOT_TRIGGER"],
    "running_kernel": os.environ["RUNNING_KERNEL"]
}))
PYEOF
