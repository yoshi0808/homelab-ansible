#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

host="${AUTOINSTALL_HOST:-<listen-address>}"
port="${AUTOINSTALL_PORT:-8080}"

echo "Serving quory autoinstall data at http://${host}:${port}/"
echo "Use kernel parameter: autoinstall ds=nocloud-net;s=http://ansy.internal:${port}/"

exec python3 -m http.server "${port}" --bind "${host}"
