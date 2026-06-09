#!/bin/bash
# radius-healthcheck.sh
# Collects FreeRADIUS health data and outputs JSON.
# Shell responsibility: collection and JSON formatting only. No judgments.

set -uo pipefail

freeradius_service_active=$(systemctl is-active freeradius 2>/dev/null) || freeradius_service_active="inactive"

if ss -H -lun 2>/dev/null | awk '{print $4}' | grep -qE ':1812$'; then
  port_1812="yes"
else
  port_1812="no"
fi

if ss -H -lun 2>/dev/null | awk '{print $4}' | grep -qE ':1813$'; then
  port_1813="yes"
else
  port_1813="no"
fi

freeradius_version=$(freeradius -v 2>&1 | grep -m1 -oE 'Version [0-9][0-9.]+' | awk '{print $2}')
if [ -z "${freeradius_version:-}" ]; then
  freeradius_version="unknown"
fi

journal_errors_raw=$(journalctl -u freeradius --since "1 hour ago" --no-pager -o short-iso 2>/dev/null | grep -E 'ERROR|FATAL' || true)

if [ -z "${journal_errors_raw:-}" ]; then
  journal_error_count=0
else
  journal_error_count=$(echo "$journal_errors_raw" | wc -l)
fi

chrony_tracking=$(chronyc tracking 2>/dev/null || echo "unavailable")

if mem_line=$(free -b 2>/dev/null | awk '/^Mem:/{print $2, $3, $7}') && [ -n "$mem_line" ]; then
  mem_total_bytes=$(echo "$mem_line" | cut -d' ' -f1)
  mem_used_bytes=$(echo "$mem_line" | cut -d' ' -f2)
  mem_available_bytes=$(echo "$mem_line" | cut -d' ' -f3)
  if [[ "$mem_total_bytes" =~ ^[0-9]+$ ]] && \
     [[ "$mem_used_bytes" =~ ^[0-9]+$ ]] && \
     [[ "$mem_available_bytes" =~ ^[0-9]+$ ]] && \
     [ "$mem_total_bytes" -gt 0 ]; then
    mem_collection_ok="true"
  else
    mem_collection_ok="false"
    mem_total_bytes=0
    mem_used_bytes=0
    mem_available_bytes=0
  fi
else
  mem_collection_ok="false"
  mem_total_bytes=0
  mem_used_bytes=0
  mem_available_bytes=0
fi

FREERADIUS_SERVICE_ACTIVE="$freeradius_service_active" \
FREERADIUS_VERSION="$freeradius_version" \
PORT_1812="$port_1812" \
PORT_1813="$port_1813" \
JOURNAL_ERROR_COUNT="$journal_error_count" \
JOURNAL_ERRORS="${journal_errors_raw}" \
CHRONY_TRACKING="$chrony_tracking" \
MEM_COLLECTION_OK="$mem_collection_ok" \
MEM_TOTAL_BYTES="$mem_total_bytes" \
MEM_USED_BYTES="$mem_used_bytes" \
MEM_AVAILABLE_BYTES="$mem_available_bytes" \
python3 - << 'PYEOF'
import json, os
from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=9))

mem_collection_ok = os.environ.get("MEM_COLLECTION_OK", "false") == "true"
mem_total = int(os.environ.get("MEM_TOTAL_BYTES", 0))
mem_used = int(os.environ.get("MEM_USED_BYTES", 0))
mem_available = int(os.environ.get("MEM_AVAILABLE_BYTES", 0))
mem_used_percent = round(mem_used / mem_total * 100) if mem_total > 0 else 0

print(json.dumps({
    "collected_at": datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S%z"),
    "freeradius": {
        "service_active": os.environ["FREERADIUS_SERVICE_ACTIVE"],
        "version": os.environ["FREERADIUS_VERSION"]
    },
    "ports": {
        "udp_1812": os.environ["PORT_1812"],
        "udp_1813": os.environ["PORT_1813"]
    },
    "journal": {
        "error_count_1h": int(os.environ["JOURNAL_ERROR_COUNT"]),
        "errors": os.environ["JOURNAL_ERRORS"]
    },
    "chrony": {
        "tracking": os.environ["CHRONY_TRACKING"]
    },
    "memory": {
        "collection_ok": mem_collection_ok,
        "total_mb": round(mem_total / 1048576),
        "used_mb": round(mem_used / 1048576),
        "available_mb": round(mem_available / 1048576),
        "used_percent": mem_used_percent
    }
}))
PYEOF
