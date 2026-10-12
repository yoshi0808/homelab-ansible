#!/usr/bin/env bash
# Start the repository's Codex roles with their fixed execution contract.
#
# The Codex binary is deliberately named here rather than discovered through
# PATH: ~/.agents/bin/codex is an agmsg shim and is not this entrypoint.
set -euo pipefail

SCRIPT_REJECT_STATUS=64
CODEX_BINARY_DEFAULT="/usr/bin/codex"
CODEX_BINARY="${CODEX_ROLE_CODEX_BINARY:-$CODEX_BINARY_DEFAULT}"
STATE_DIR="${CODEX_ROLE_STATE_DIR:-$HOME/.local/state/codex-role}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Keep the role values in these two arrays: check-doc-consistency.py reads the
# staged definitions below and compares them with coordinator.md.
declare -Ar ROLE_MODEL=(
    [implementer]="gpt-5.6-terra"
    [plan-reviewer]="gpt-5.6-sol"
    [auditor]="gpt-5.6-sol"
)
declare -Ar ROLE_EFFORT=(
    [implementer]="medium"
    [plan-reviewer]="medium"
    [auditor]="medium"
)
declare -Ar ROLE_SANDBOX=(
    [implementer]="workspace-write"
    [plan-reviewer]="read-only"
    [auditor]="read-only"
)
declare -Ar ROLE_DOCUMENT=(
    [implementer]="docs/ai/roles/implementer.md"
    [plan-reviewer]="docs/ai/roles/reviewer.md"
    [auditor]="docs/ai/roles/auditor.md"
)
declare -Ar ROLE_LABEL=(
    [implementer]="Implementer"
    [plan-reviewer]="計画Reviewer"
    [auditor]="Auditor"
)

usage() {
    cat >&2 <<'USAGE'
Usage:
  codex-role.sh implementer|plan-reviewer [--effort high] --output FILE [--prompt FILE]
  codex-role.sh implementer|plan-reviewer --resume SESSION_ID [--effort high] --output FILE [--prompt FILE]
  codex-role.sh auditor --case-dir docs/ai/reviews/TARGET --start-at PATH --output FILE

For Implementer and plan-reviewer, omit --prompt to read the request from
standard input. Only Implementer may use --effort high. Auditor accepts no
free-form request and cannot resume.
USAGE
}

die() {
    echo "codex-role.sh: $*" >&2
    exit "$SCRIPT_REJECT_STATUS"
}

canonical_binary() {
    local candidate="$1"
    if [[ "$candidate" == "~/"* ]]; then
        candidate="$HOME/${candidate#~/}"
    fi
    realpath -m -- "$candidate"
}

assert_safe_binary() {
    local resolved
    resolved="$(canonical_binary "$CODEX_BINARY")" || die "cannot resolve Codex binary: $CODEX_BINARY"
    case "$resolved" in
        "$HOME"/.agents|"$HOME"/.agents/*)
            die "refusing Codex binary below ~/.agents/: $resolved"
            ;;
    esac
    [[ -x "$resolved" ]] || die "Codex binary is not executable: $resolved"
    CODEX_BINARY="$resolved"
}

validate_session_id() {
    [[ "$1" =~ ^[[:alnum:]][[:alnum:]-]*$ ]] || die "invalid session id"
}

validate_effort_for_role() {
    local role="$1" effort="$2"
    [[ "$effort" == "medium" || ("$role" == "implementer" && "$effort" == "high") ]]
}

read_session_role() {
    local session_id="$1" record stored_role stored_effort extra
    validate_session_id "$session_id"
    record="$STATE_DIR/$session_id"
    [[ -f "$record" ]] || die "no role record for session id: $session_id"
    IFS=$'\t' read -r stored_role stored_effort extra < "$record"
    [[ -n "$stored_role" && -z "$extra" ]] || die "malformed role record for session id: $session_id"
    [[ "$stored_role" == "$ROLE" ]] || die "session id $session_id belongs to $stored_role, not $ROLE"
    # Role-only records were written before effort became session state. They
    # mean that role's historical default rather than an ambiguous fallback.
    if [[ -z "$stored_effort" ]]; then
        stored_effort="${ROLE_EFFORT[$ROLE]}"
    fi
    validate_effort_for_role "$ROLE" "$stored_effort" \
        || die "malformed effort in role record for session id: $session_id"
    if [[ "$EFFORT_REQUESTED" == true && "$EFFORT" != "$stored_effort" ]]; then
        die "--effort conflicts with recorded effort for session id: $session_id"
    fi
    EFFORT="$stored_effort"
}

record_session_role() {
    local session_id="$1" record
    [[ "$session_id" =~ ^[[:alnum:]][[:alnum:]-]*$ ]] || return 1
    validate_effort_for_role "$ROLE" "$EFFORT" || return 1
    umask 077
    mkdir -p -- "$STATE_DIR" || return 1
    record="$STATE_DIR/$session_id"
    if [[ -e "$record" ]]; then
        return 1
    fi
    printf '%s\t%s\n' "$ROLE" "$EFFORT" > "$record"
}

extract_session_id() {
    sed -nE '/^[[:space:]]*session id:[[:space:]]*[[:alnum:]-]+[[:space:]]*$/ { s/^[[:space:]]*session id:[[:space:]]*([[:alnum:]-]+)[[:space:]]*$/\1/; p; q; }' "$1"
}

has_non_whitespace() {
    grep -q '[^[:space:]]' "$1"
}

require_auditor_path() {
    local supplied="$1" kind="$2" absolute
    [[ "$supplied" == docs/ai/reviews/* ]] || die "$kind must be below docs/ai/reviews/"
    absolute="$(realpath -e -- "$REPO_ROOT/$supplied")" \
        || die "$kind does not exist: $supplied"
    [[ "$absolute" == "$REPO_ROOT"/docs/ai/reviews/* ]] \
        || die "$kind escapes docs/ai/reviews/: $supplied"
    printf '%s\n' "$absolute"
}

ROLE="${1:-}"
[[ -n "$ROLE" ]] || { usage; die "role is required"; }
shift
[[ -n "${ROLE_MODEL[$ROLE]+set}" ]] || { usage; die "unknown role: $ROLE"; }

PROMPT_SOURCE=""
OUTPUT_FILE=""
RESUME_SESSION=""
EFFORT="${ROLE_EFFORT[$ROLE]}"
EFFORT_REQUESTED=false
CASE_DIR=""
START_AT=""

while (($#)); do
    case "$1" in
        --prompt)
            (($# >= 2)) || die "--prompt requires a file"
            PROMPT_SOURCE="$2"
            shift 2
            ;;
        --output)
            (($# >= 2)) || die "--output requires a file"
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --resume)
            (($# >= 2)) || die "--resume requires a session id"
            RESUME_SESSION="$2"
            shift 2
            ;;
        --effort)
            (($# >= 2)) || die "--effort requires a value"
            [[ "$2" == "high" && "$ROLE" == "implementer" ]] \
                || die "only Implementer may use --effort high"
            EFFORT="high"
            EFFORT_REQUESTED=true
            shift 2
            ;;
        --case-dir)
            (($# >= 2)) || die "--case-dir requires a path"
            CASE_DIR="$2"
            shift 2
            ;;
        --start-at)
            (($# >= 2)) || die "--start-at requires a path"
            START_AT="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            usage
            die "unknown argument: $1"
            ;;
    esac
done

[[ -n "$OUTPUT_FILE" ]] || die "--output is required"
# Resolve while the caller's cwd is still active. Codex itself runs from the
# repository root below, but --output remains a caller-relative destination.
OUTPUT_FILE="$(realpath -m -- "$OUTPUT_FILE")" || die "cannot resolve output path: $OUTPUT_FILE"
assert_safe_binary

# Validate a continuation before reading a potentially large request. This
# keeps a missing or cross-role session from being obscured by unrelated input
# errors and, more importantly, rejects it before Codex can be invoked.
if [[ "$ROLE" != "auditor" && -n "$RESUME_SESSION" ]]; then
    read_session_role "$RESUME_SESSION"
fi

PROMPT_FILE="$(mktemp "${TMPDIR:-/tmp}/codex-role-prompt.XXXXXX")"
RUN_LOG="$(mktemp "${TMPDIR:-/tmp}/codex-role-output.XXXXXX")"
cleanup() { rm -f -- "$PROMPT_FILE" "$RUN_LOG"; }
trap cleanup EXIT

if [[ "$ROLE" == "auditor" ]]; then
    [[ -z "$PROMPT_SOURCE" ]] || die "Auditor does not accept --prompt"
    [[ -z "$RESUME_SESSION" ]] || die "Auditor cannot resume"
    [[ -n "$CASE_DIR" && -n "$START_AT" ]] || die "Auditor requires --case-dir and --start-at"
    case_absolute="$(require_auditor_path "$CASE_DIR" "case directory")"
    [[ -d "$case_absolute" ]] || die "--case-dir is not a directory: $CASE_DIR"
    start_absolute="$(require_auditor_path "$START_AT" "start path")"
    [[ -f "$start_absolute" && "$start_absolute" == "$case_absolute"/* ]] \
        || die "--start-at must be a file within --case-dir"
    case_relative="${case_absolute#"$REPO_ROOT"/}"
    start_relative="${start_absolute#"$REPO_ROOT"/}"
    cat > "$PROMPT_FILE" <<EOF
あなたはこのリポジトリの${ROLE_LABEL[$ROLE]}です。まず docs/ai/core.md と ${ROLE_DOCUMENT[$ROLE]} を読んでください。

監査対象の案件フォルダ: ${case_relative}
読み始める場所: ${start_relative}
EOF
else
    [[ -z "$CASE_DIR" && -z "$START_AT" ]] || die "--case-dir/--start-at are only for Auditor"
    if [[ -n "$PROMPT_SOURCE" ]]; then
        [[ -f "$PROMPT_SOURCE" ]] || die "prompt file does not exist: $PROMPT_SOURCE"
        [[ -s "$PROMPT_SOURCE" ]] && has_non_whitespace "$PROMPT_SOURCE" \
            || die "prompt file is empty or whitespace-only: $PROMPT_SOURCE"
    else
        PROMPT_SOURCE="$(mktemp "${TMPDIR:-/tmp}/codex-role-request.XXXXXX")"
        trap 'rm -f -- "$PROMPT_FILE" "$RUN_LOG" "$PROMPT_SOURCE"' EXIT
        cat > "$PROMPT_SOURCE"
        [[ -s "$PROMPT_SOURCE" ]] && has_non_whitespace "$PROMPT_SOURCE" \
            || die "request is empty or whitespace-only"
    fi
    {
        printf 'あなたはこのリポジトリの%sです。まず docs/ai/core.md と %s を読んでください。\n\n' \
            "${ROLE_LABEL[$ROLE]}" "${ROLE_DOCUMENT[$ROLE]}"
        cat -- "$PROMPT_SOURCE"
    } > "$PROMPT_FILE"
fi

MODEL="${ROLE_MODEL[$ROLE]}"
SANDBOX="${ROLE_SANDBOX[$ROLE]}"
if [[ -n "$RESUME_SESSION" ]]; then
    COMMAND=("$CODEX_BINARY" exec resume "$RESUME_SESSION" -m "$MODEL"
             -c "model_reasoning_effort=$EFFORT" -c "sandbox_mode=\"$SANDBOX\""
             -c "sandbox_workspace_write.network_access=false"
             -o "$OUTPUT_FILE" -)
else
    COMMAND=("$CODEX_BINARY" exec -m "$MODEL" -c "model_reasoning_effort=$EFFORT"
             -s "$SANDBOX" -c "sandbox_workspace_write.network_access=false"
             -o "$OUTPUT_FILE" -)
fi

# Both exec forms must see the repository as their working tree. Do this only
# after reading a caller-relative --prompt file and composing the temp prompt.
cd -- "$REPO_ROOT" || die "cannot change to repository root: $REPO_ROOT"

set +e
"${COMMAND[@]}" < "$PROMPT_FILE" 2>&1 | tee "$RUN_LOG"
PIPELINE_STATUS=("${PIPESTATUS[@]}")
CODEX_STATUS=${PIPELINE_STATUS[0]}
TEE_STATUS=${PIPELINE_STATUS[1]}
set -e
[[ "$TEE_STATUS" -eq 0 ]] || die "cannot retain Codex output"

if [[ -z "$RESUME_SESSION" ]]; then
    SESSION_ID="$(extract_session_id "$RUN_LOG")"
    if [[ -n "$SESSION_ID" ]]; then
        if ! record_session_role "$SESSION_ID"; then
            echo "codex-role.sh: cannot record session role: $SESSION_ID" >&2
            [[ "$CODEX_STATUS" -ne 0 ]] && exit "$CODEX_STATUS"
            die "cannot record session role: $SESSION_ID"
        fi
        printf 'codex-role session id: %s\n' "$SESSION_ID"
    elif [[ "$CODEX_STATUS" -eq 0 ]]; then
        die "Codex completed without a parseable session id"
    fi
fi

[[ "$CODEX_STATUS" -eq 0 ]] || exit "$CODEX_STATUS"
