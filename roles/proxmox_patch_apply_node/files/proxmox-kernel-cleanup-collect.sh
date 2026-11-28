#!/bin/bash
# Collect only; classification and mutation are deliberately in Ansible.
set -uo pipefail

capture() {
  local output rc
  output="$("$@" 2>&1)"
  rc=$?
  OUTPUT="$output" RC="$rc" python3 - <<'PYEOF'
import base64, json, os
print(json.dumps({"rc": int(os.environ["RC"]),
                  "output": base64.b64encode(os.environ["OUTPUT"].encode()).decode()}))
PYEOF
}

printf '{"running_kernel":'
uname -r | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()), end="")'
printf ',"packages":'
capture /usr/bin/dpkg-query -W '-f=${db:Status-Abbrev}\t${Package}\t${Version}\n' 'proxmox-kernel-*' 'proxmox-default-kernel' 'proxmox-ve'
printf ',"boot_tool":'
capture /usr/sbin/proxmox-boot-tool kernel list
printf '}'
