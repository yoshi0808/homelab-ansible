#!/usr/bin/env bash
# recovery-push-dispatch.sh: SSH forced command handler on quory.
# Invoked when authy/monnie OnFailure trigger SSHes in as recovery-exec.
# TARGET is hardcoded in authorized_keys forced command — no user-supplied input.
set -euo pipefail

TARGET="${1:?usage: recovery-push-dispatch.sh <target>}"
MUTE_DIR="/var/lib/homelab-recovery/mute"
STATE_DIR="/var/lib/homelab-recovery/push"
LOCK_DIR="${STATE_DIR}/${TARGET}.lock"
WORKSPACE="/var/lib/recovery-exec/workspace"
WRAPPER="/usr/local/bin/codex-exec-wrapper"

log() {
    printf '%s PUSH %s: %s\n' \
        "$(TZ='Asia/Tokyo' date '+%Y-%m-%dT%H:%M:%S+09:00')" \
        "$TARGET" "$*" \
        >> "${STATE_DIR}/dispatch.log"
}

# Mute check (mute files are 0644 world-readable)
mute_file="${MUTE_DIR}/${TARGET}.json"
if [[ -f "$mute_file" ]]; then
    until_str=$(python3 -c \
        "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('until',''))" \
        "$mute_file" 2>/dev/null || true)
    if [[ -n "$until_str" ]]; then
        until_epoch=$(date -d "$until_str" +%s 2>/dev/null || echo 0)
        now=$(date +%s)
        if (( until_epoch > now )); then
            reason=$(python3 -c \
                "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('reason',''))" \
                "$mute_file" 2>/dev/null || true)
            remaining=$(( (until_epoch - now + 59) / 60 ))
            log "muted (残 ${remaining} 分, ${reason}) — skip"
            exit 0
        fi
    fi
fi

# Push session lock: prevent parallel Codex sessions for same target
if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
    log "push session already running — skip"
    exit 0
fi
trap 'rmdir "${LOCK_DIR}" 2>/dev/null || true; log "session ended"' EXIT

log "firing: Codex investigation for ${TARGET}"

"${WRAPPER}" exec --cd "${WORKSPACE}" \
    "${TARGET} でサービス障害を OnFailure で検知しました。調査・復旧してください。"
