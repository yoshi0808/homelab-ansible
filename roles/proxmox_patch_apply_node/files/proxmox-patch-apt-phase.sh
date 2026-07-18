#!/bin/bash
# Run one apt phase with a persistent combined stdout/stderr log.
# The download phase may temporarily pin a runtime-selected CDN address.

set -euo pipefail
umask 027

phase=${1:-}
log_path=${2:-}
mirror_host=${3:-}
mirror_address=${4:-}

if [[ "$phase" != "download" && "$phase" != "apply" ]]; then
  echo "phase must be download or apply" >&2
  exit 64
fi
if [[ "$log_path" != /* || ! -d "$(dirname -- "$log_path")" ]]; then
  echo "log path must be absolute and its parent must exist" >&2
  exit 64
fi
if [[ -n "$mirror_host" && ! "$mirror_host" =~ ^[A-Za-z0-9.-]+$ ]]; then
  echo "invalid mirror host" >&2
  exit 64
fi
if [[ -n "$mirror_address" && ! "$mirror_address" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
  echo "invalid runtime mirror address" >&2
  exit 64
fi

: > "$log_path"
/bin/chmod 0640 "$log_path"

hosts_backup=""
hosts_candidate=""

restore_hosts() {
  local restore_rc=0

  if [[ -n "$hosts_backup" && -e "$hosts_backup" ]]; then
    if ! /bin/mv -f -- "$hosts_backup" /etc/hosts; then
      restore_rc=90
      echo "FATAL: failed to atomically restore /etc/hosts" | /usr/bin/tee -a "$log_path" >&2
    fi
  fi
  if [[ -n "$hosts_candidate" && -e "$hosts_candidate" ]]; then
    /bin/rm -f -- "$hosts_candidate" || true
  fi
  return "$restore_rc"
}

on_exit() {
  local command_rc=$?
  local restore_rc=0

  trap - EXIT HUP INT TERM
  restore_hosts || restore_rc=$?
  if (( restore_rc != 0 )); then
    exit "$restore_rc"
  fi
  exit "$command_rc"
}

trap on_exit EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "$phase" == "download" ]]; then
  if [[ -z "$mirror_host" || ! -f /etc/hosts || -L /etc/hosts ]]; then
    echo "cannot safely download: /etc/hosts must be a regular non-symlink file; manual recovery required" \
      | /usr/bin/tee -a "$log_path" >&2
    exit 65
  fi
  if /bin/grep -q 'temporary-proxmox-patch-mirror' /etc/hosts; then
    echo "retained temporary mirror marker found in /etc/hosts; manual recovery required before download" \
      | /usr/bin/tee -a "$log_path" >&2
    exit 66
  fi

  if [[ -n "$mirror_address" ]]; then
    hosts_backup=$(/usr/bin/mktemp /etc/.hosts.proxmox-patch.backup.XXXXXX)
    hosts_candidate=$(/usr/bin/mktemp /etc/.hosts.proxmox-patch.candidate.XXXXXX)
    /bin/cp --preserve=all -- /etc/hosts "$hosts_backup"
    /bin/cp --preserve=all -- /etc/hosts "$hosts_candidate"
    printf '\n%s %s # temporary-proxmox-patch-mirror\n' "$mirror_address" "$mirror_host" >> "$hosts_candidate"
    /bin/mv -f -- "$hosts_candidate" /etc/hosts
    hosts_candidate=""
  fi
fi

started_epoch=$(/usr/bin/date +%s)
set +e
if [[ "$phase" == "download" ]]; then
  DEBIAN_FRONTEND=noninteractive LC_ALL=C \
    /usr/bin/apt-get -y -d dist-upgrade 2>&1 | /usr/bin/tee "$log_path"
else
  DEBIAN_FRONTEND=noninteractive LC_ALL=C \
    /usr/bin/apt-get -y dist-upgrade 2>&1 | /usr/bin/tee "$log_path"
fi
apt_rc=${PIPESTATUS[0]}
set -e
finished_epoch=$(/usr/bin/date +%s)
elapsed_seconds=$((finished_epoch - started_epoch))

if [[ "$phase" == "download" ]]; then
  download_bytes=$(/usr/bin/awk '
    $1 == "Fetched" {
      value = $2
      unit = $3
      gsub(/,/, "", value)
    }
    END {
      multiplier = 1
      if (unit == "kB") multiplier = 1000
      else if (unit == "MB") multiplier = 1000000
      else if (unit == "GB") multiplier = 1000000000
      if (value == "") value = 0
      printf "%.0f", value * multiplier
    }
  ' "$log_path")
  cache_hit=false
  if /bin/grep -Eq '^Need to get 0 B([ /]|$)' "$log_path"; then
    cache_hit=true
  fi
  {
    printf 'PROXMOX_PATCH_DOWNLOAD_BYTES=%s\n' "$download_bytes"
    printf 'PROXMOX_PATCH_DOWNLOAD_SECONDS=%s\n' "$elapsed_seconds"
    printf 'PROXMOX_PATCH_CACHE_HIT=%s\n' "$cache_hit"
  } | /usr/bin/tee -a "$log_path"
else
  printf 'PROXMOX_PATCH_APPLY_SECONDS=%s\n' "$elapsed_seconds" | /usr/bin/tee -a "$log_path"
fi

exit "$apt_rc"
