#!/bin/bash
# monitoring-healthcheck.sh
# Collects Prometheus / Grafana / Loki health data and outputs JSON.
# Shell responsibility: collection and JSON formatting only. No judgments.

set -uo pipefail

prometheus_service_active=$(systemctl is-active prometheus 2>/dev/null) || prometheus_service_active="inactive"
grafana_service_active=$(systemctl is-active grafana-server 2>/dev/null) || grafana_service_active="inactive"
loki_service_active=$(systemctl is-active loki 2>/dev/null) || loki_service_active="inactive"

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

PROMETHEUS_SERVICE_ACTIVE="$prometheus_service_active" \
GRAFANA_SERVICE_ACTIVE="$grafana_service_active" \
LOKI_SERVICE_ACTIVE="$loki_service_active" \
PORT_9090="$port_9090" \
PORT_3000="$port_3000" \
PORT_3100="$port_3100" \
python3 - << 'PYEOF'
import json, os
from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=9))

print(json.dumps({
    "collected_at": datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S%z"),
    "services": {
        "prometheus": os.environ["PROMETHEUS_SERVICE_ACTIVE"],
        "grafana": os.environ["GRAFANA_SERVICE_ACTIVE"],
        "loki": os.environ["LOKI_SERVICE_ACTIVE"]
    },
    "ports": {
        "tcp_9090": os.environ["PORT_9090"],
        "tcp_3000": os.environ["PORT_3000"],
        "tcp_3100": os.environ["PORT_3100"]
    }
}))
PYEOF
