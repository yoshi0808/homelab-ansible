#!/bin/bash
# Copy deb archives to/from the optional NAS cache, or prune old date keys.

set -euo pipefail
umask 027

operation=${1:-}
source_path=${2:-}
destination_or_keep=${3:-}
cache_root=${4:-}

require_safe_directory() {
  local path=$1
  local normalized
  normalized=$(/usr/bin/readlink -m -- "$path")
  if [[ "$path" != /* || "$path" == "/" || "$path" == "/var" || "$path" == "/mnt" ]]; then
    echo "refusing unsafe directory: $path" >&2
    exit 64
  fi
  if [[ -L "$path" || "$path" != "$normalized" || ! "$path" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
    echo "refusing non-canonical directory: $path" >&2
    exit 64
  fi
}

require_existing_directory() {
  local path=$1
  require_safe_directory "$path"
  if [[ ! -d "$path" || -L "$path" ]]; then
    echo "refusing non-directory or symlink: $path" >&2
    exit 64
  fi
}

require_mount_root() {
  local mount_root=$1
  require_existing_directory "$mount_root"
  if [[ ! "$mount_root" =~ ^/mnt/pve/[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$ ]]; then
    echo "refusing unsafe mount root: $mount_root" >&2
    exit 64
  fi
}

require_cache_root_pattern() {
  require_safe_directory "$cache_root"
  if [[ ! "$cache_root" =~ ^/mnt/pve/[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?/proxmox-patch-cache$ ]]; then
    echo "refusing cache root outside a single /mnt/pve storage: $cache_root" >&2
    exit 64
  fi
}

require_cache_root() {
  require_cache_root_pattern
  require_existing_directory "$cache_root"
}

require_date_directory() {
  local path=$1
  local date_key
  require_safe_directory "$path"
  if [[ "$path" != "$cache_root/"* ]]; then
    echo "refusing cache date directory outside validated root: $path" >&2
    exit 64
  fi
  date_key=${path#"$cache_root/"}
  if [[ ! "$date_key" =~ ^20[0-9]{6}$ ]]; then
    echo "refusing invalid cache date key: $date_key" >&2
    exit 64
  fi
}

copy_debs() {
  local from_dir=$1
  local to_dir=$2
  local copied=0
  local archive

  require_safe_directory "$from_dir"
  require_safe_directory "$to_dir"
  [[ -d "$from_dir" && -d "$to_dir" ]]

  shopt -s nullglob
  for archive in "$from_dir"/*.deb; do
    if [[ ! -f "$archive" || -L "$archive" ]]; then
      continue
    fi
    if [[ -L "$to_dir/${archive##*/}" ]]; then
      echo "refusing symlink destination: $to_dir/${archive##*/}" >&2
      exit 65
    fi
    if [[ ! -e "$to_dir/${archive##*/}" ]]; then
      /bin/cp --update=none -- "$archive" "$to_dir/"
      copied=$((copied + 1))
    fi
  done
  printf 'operation=%s copied=%s\n' "$operation" "$copied"
}

case "$operation" in
  prepare)
    mount_root=$source_path
    date_directory=$destination_or_keep
    created=0

    require_mount_root "$mount_root"
    require_cache_root_pattern
    if [[ "$cache_root" != "$mount_root/proxmox-patch-cache" ]]; then
      echo "cache root must be the direct configured subtree of the mount root" >&2
      exit 64
    fi
    require_date_directory "$date_directory"

    if [[ -e "$cache_root" || -L "$cache_root" ]]; then
      require_existing_directory "$cache_root"
    else
      /bin/mkdir --mode=0750 -- "$cache_root"
      created=$((created + 1))
    fi
    require_mount_root "$mount_root"
    require_cache_root

    if [[ -e "$date_directory" || -L "$date_directory" ]]; then
      require_existing_directory "$date_directory"
    else
      /bin/mkdir --mode=0750 -- "$date_directory"
      created=$((created + 1))
    fi
    require_mount_root "$mount_root"
    require_cache_root
    require_date_directory "$date_directory"
    require_existing_directory "$date_directory"
    printf 'operation=prepare created=%s\n' "$created"
    ;;
  seed)
    require_cache_root
    require_date_directory "$source_path"
    if [[ "$destination_or_keep" != "/var/cache/apt/archives" ]]; then
      echo "seed destination must be /var/cache/apt/archives" >&2
      exit 64
    fi
    copy_debs "$source_path" "$destination_or_keep"
    ;;
  publish)
    require_cache_root
    if [[ "$source_path" != "/var/cache/apt/archives" ]]; then
      echo "publish source must be /var/cache/apt/archives" >&2
      exit 64
    fi
    require_date_directory "$destination_or_keep"
    copy_debs "$source_path" "$destination_or_keep"
    ;;
  prune)
    require_cache_root
    if [[ "$source_path" != "$cache_root" ]]; then
      echo "prune source must equal the validated cache root" >&2
      exit 64
    fi
    if [[ ! "$destination_or_keep" =~ ^[1-9][0-9]*$ || ! -d "$source_path" ]]; then
      echo "prune requires an existing cache directory and keep >= 1" >&2
      exit 64
    fi

    mapfile -t date_keys < <(
      /usr/bin/find "$source_path" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' \
        | /bin/grep -E '^20[0-9]{6}$' \
        | /usr/bin/sort
    )
    remove_count=$((${#date_keys[@]} - destination_or_keep))
    if (( remove_count < 0 )); then
      remove_count=0
    fi
    for ((index = 0; index < remove_count; index++)); do
      date_key=${date_keys[$index]}
      [[ "$date_key" =~ ^20[0-9]{6}$ ]]
      /bin/rm -rf --one-file-system -- "$source_path/$date_key"
    done
    printf 'operation=prune removed=%s kept=%s\n' "$remove_count" "$destination_or_keep"
    ;;
  *)
    echo "operation must be prepare, seed, publish, or prune" >&2
    exit 64
    ;;
esac
