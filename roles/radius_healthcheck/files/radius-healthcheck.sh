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

FREERADIUS_SERVICE_ACTIVE="$freeradius_service_active" \
FREERADIUS_VERSION="$freeradius_version" \
PORT_1812="$port_1812" \
PORT_1813="$port_1813" \
JOURNAL_ERROR_COUNT="$journal_error_count" \
JOURNAL_ERRORS="${journal_errors_raw}" \
CHRONY_TRACKING="$chrony_tracking" \
python3 - << 'PYEOF'
import json, os
from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=9))

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
    }
}))
PYEOF
