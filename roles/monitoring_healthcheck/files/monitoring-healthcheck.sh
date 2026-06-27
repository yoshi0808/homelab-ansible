#!/bin/bash
# monitoring-healthcheck.sh
# Collects Prometheus / Grafana / Loki health data and outputs JSON.
# Shell responsibility: collection and JSON formatting only. No judgments.

set -uo pipefail

prometheus_service_active=$(systemctl is-active prometheus 2>/dev/null) || prometheus_service_active="inactive"
grafana_service_active=$(systemctl is-active grafana-server 2>/dev/null) || grafana_service_active="inactive"
loki_service_active=$(systemctl is-active loki 2>/dev/null) || loki_service_active="inactive"
unpoller_service_active=$(systemctl is-active unpoller 2>/dev/null) || unpoller_service_active="inactive"

if ss -H -ltn 2>/dev/null | awk '{print $4}' | grep -qE ':9090$'; then
  port_9090="yes"
else
  port_9090="no"
fi

if ss -H -ltn 2>/dev/null | awk '{print $4}' | grep -qE ':3000$'; then
  port_3000="yes"
else
  port_3000="no"
fi

if ss -H -ltn 2>/dev/null | awk '{print $4}' | grep -qE ':3100$'; then
  port_3100="yes"
else
  port_3100="no"
fi

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

PROMETHEUS_SERVICE_ACTIVE="$prometheus_service_active" \
GRAFANA_SERVICE_ACTIVE="$grafana_service_active" \
LOKI_SERVICE_ACTIVE="$loki_service_active" \
UNPOLLER_SERVICE_ACTIVE="$unpoller_service_active" \
PORT_9090="$port_9090" \
PORT_3000="$port_3000" \
PORT_3100="$port_3100" \
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
    "services": {
        "prometheus": os.environ["PROMETHEUS_SERVICE_ACTIVE"],
        "grafana": os.environ["GRAFANA_SERVICE_ACTIVE"],
        "loki": os.environ["LOKI_SERVICE_ACTIVE"],
        "unpoller": os.environ["UNPOLLER_SERVICE_ACTIVE"]
    },
    "ports": {
        "tcp_9090": os.environ["PORT_9090"],
        "tcp_3000": os.environ["PORT_3000"],
        "tcp_3100": os.environ["PORT_3100"]
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
