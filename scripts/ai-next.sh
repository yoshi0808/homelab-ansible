#!/usr/bin/env bash
# =============================================================
# ai-next.sh - homelab-ansible AI workflow prompt generator
#
# Usage:
#   ./scripts/ai-next.sh              # auto-detect next step
#   ./scripts/ai-next.sh final        # create final.md (auto-detect target)
#   ./scripts/ai-next.sh final <target>  # create final.md for specified target
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REVIEWS_DIR="$REPO_ROOT/docs/ai/reviews"
PROMPTS_DIR="$REPO_ROOT/docs/ai/prompts"
CORE_MD="$PROMPTS_DIR/core.md"

# =============================================================
# Utilities
# =============================================================

detect_policy() {
    local target="$1"
    local policy_file=""

    if [[ "$target" == proxmox_* ]]; then
        policy_file="$PROMPTS_DIR/proxmox_patch_policy.md"
    else
        policy_file="$PROMPTS_DIR/ubuntu_vm_patch_policy.md"
    fi

    [ -f "$policy_file" ] && echo "$policy_file" || echo ""
}

detect_step() {
    local dir="$1"
    local latest=""
    latest=$(ls "$dir"/*.md 2>/dev/null | sort | tail -1 || true)

    case "$latest" in
        *_implement.md)   echo "review" ;;
        *_review.md)      echo "reimplement" ;;
        *_requirement.md) echo "implement" ;;
        *)                echo "none" ;;
    esac
}

next_num() {
    local dir="$1"
    local last_num="000"
    local latest
    latest=$(ls "$dir"/*.md 2>/dev/null | sort | tail -1 || true)

    if [ -n "$latest" ]; then
        last_num=$(basename "$latest" | cut -d'_' -f2 || echo "000")
    fi
    printf "%03d" $((10#$last_num + 1))
}

rel() {
    echo "${1#$REPO_ROOT/}"
}

copy_clipboard() {
    local text="$1"

    # pbcopy first (macOS)
    if command -v pbcopy &>/dev/null; then
        printf '%s' "$text" | pbcopy
        return
    fi

    # xclip / xsel fallback (Linux)
    if command -v xclip &>/dev/null; then
        printf '%s' "$text" | xclip -selection clipboard
        return
    fi
    if command -v xsel &>/dev/null; then
        printf '%s' "$text" | xsel --clipboard --input
        return
    fi

    # OSC 52 fallback (tmux / SSH)
    local encoded
    encoded=$(printf '%s' "$text" | base64 | tr -d '\n')
    printf '\033]52;c;%s\a' "$encoded" > /dev/tty
}

# =============================================================
# Status list
# =============================================================

show_status() {
    echo ""
    echo "=== homelab-ansible AI workflow status ==="
    echo ""

    local found=0
    for dir in "$REVIEWS_DIR"/*/; do
        [ -d "$dir" ] || continue
        local target step latest
        target=$(basename "$dir")
        step=$(detect_step "$dir")
        latest=$(ls "$dir"/*.md 2>/dev/null | sort | tail -1 \
            | xargs -r basename 2>/dev/null || echo "-")

        printf "  %-35s latest: %-45s next: %s\n" "$target" "$latest" "$step"
        found=1
    done

    [ $found -eq 0 ] && echo "  (no review directories found)"
    echo ""
}

# =============================================================
# Select active target
# =============================================================

select_active_target() {
    local active_targets=()
    local active_steps=()

    for dir in "$REVIEWS_DIR"/*/; do
        [ -d "$dir" ] || continue
        local target step
        target=$(basename "$dir")
        step=$(detect_step "$dir")
        if [ "$step" != "none" ]; then
            active_targets+=("$target")
            active_steps+=("$step")
        fi
    done

    case ${#active_targets[@]} in
      0)
        echo "INFO: no active tasks found" >&2
        exit 0
        ;;
      1)
        echo "-> target: ${active_targets[0]}" >&2
        echo "-> step  : ${active_steps[0]}" >&2
        echo "${active_targets[0]} ${active_steps[0]}"
        ;;
      *)
        echo "" >&2
        echo "Multiple active tasks found:" >&2
        echo "" >&2
        for i in "${!active_targets[@]}"; do
            printf "  %d) %-35s -> %s\n" $((i+1)) "${active_targets[$i]}" "${active_steps[$i]}" >&2
        done
        echo "" >&2
        read -rp "Select number: " choice < /dev/tty
        local idx=$((choice - 1))
        if [ $idx -lt 0 ] || [ $idx -ge ${#active_targets[@]} ]; then
            echo "ERROR: invalid number: $choice" >&2
            exit 1
        fi
        echo "-> selected: ${active_targets[$idx]} (${active_steps[$idx]})" >&2
        echo "${active_targets[$idx]} ${active_steps[$idx]}"
        ;;
    esac
}

# =============================================================
# Create final.md
# =============================================================

create_final() {
    local target="$1"
    local target_dir="$REVIEWS_DIR/$target"
    local date num save

    if [ ! -d "$target_dir" ]; then
        echo "ERROR: directory not found: $target_dir"
        exit 1
    fi

    date=$(date +%Y-%m-%d)
    num=$(next_num "$target_dir")
    save="$target_dir/${date}_${num}_final.md"

    cat > "$save" << EOF
# Final

Confirmed.

Reviewer: Yoshinobu
Date: $date

## Target

- $target

## Comments

EOF

    echo ""
    echo "Created: $(rel "$save")"
    echo "Opening in VS Code..."
    echo ""
    code "$save" 2>/dev/null || echo "  -> Please open: $(rel "$save")"
}

# =============================================================
# Prompt generation
# =============================================================

generate_review_prompt() {
    local target="$1" policy="$2"
    local target_dir="$REVIEWS_DIR/$target"
    local date num req impl save

    date=$(date +%Y-%m-%d)
    num=$(next_num "$target_dir")
    req=$(ls "$target_dir"/*_requirement.md 2>/dev/null | sort | tail -1 || true)
    impl=$(ls "$target_dir"/*_implement.md 2>/dev/null | sort | tail -1 || true)
    save="$target_dir/${date}_${num}_review.md"

    [ -z "$req" ]  && { echo "ERROR: requirement.md not found" >&2; exit 1; }
    [ -z "$impl" ] && { echo "ERROR: implement.md not found" >&2; exit 1; }

    local prompt
    prompt="# This prompt is for Codex.
# If you are Claude Code, do NOT execute this prompt.
# Tell the user: 'Please send this to Codex.' and stop.

First, create the following file:

- $(rel "$save")

Then read the files below, review the git diff, and write the results into that file.

- $(rel "$CORE_MD")
- $(rel "$req")
- $(rel "$impl")"

    [ -n "$policy" ] && prompt+="
- $(rel "$policy")"

    prompt+="

Please answer in Japanese."

    echo "$prompt"
}

generate_reimplement_prompt() {
    local target="$1" policy="$2"
    local target_dir="$REVIEWS_DIR/$target"
    local date num req rev save

    date=$(date +%Y-%m-%d)
    num=$(next_num "$target_dir")
    req=$(ls "$target_dir"/*_requirement.md 2>/dev/null | sort | tail -1 || true)
    rev=$(ls "$target_dir"/*_review.md 2>/dev/null | sort | tail -1 || true)
    save="$target_dir/${date}_${num}_implement.md"

    [ -z "$req" ] && { echo "ERROR: requirement.md not found" >&2; exit 1; }
    [ -z "$rev" ] && { echo "ERROR: review.md not found" >&2; exit 1; }

    local prompt
    prompt="# This prompt is for Claude Code.
# If you are Codex, do NOT execute this prompt.
# Tell the user: 'Please send this to Claude Code.' and stop.

First, create the following file:

- $(rel "$save")

Then read the files below, re-implement accordingly, and write the implementation summary into that file.

- $(rel "$CORE_MD")
- $(rel "$req")
- $(rel "$rev")"

    [ -n "$policy" ] && prompt+="
- $(rel "$policy")"

    prompt+="

Please answer in Japanese."

    echo "$prompt"
}

# =============================================================
# Main
# =============================================================

ARG1="${1:-}"
ARG2="${2:-}"

# final
if [ "$ARG1" = "final" ]; then
    if [ -n "$ARG2" ]; then
        TARGET="$ARG2"
    else
        SELECTION="$(select_active_target)"
        if [ -z "$SELECTION" ]; then show_status; exit 0; fi
        read -r TARGET _ <<< "$SELECTION"
    fi
    create_final "$TARGET"
    exit 0
fi

# auto
SELECTION="$(select_active_target)"
if [ -z "$SELECTION" ]; then show_status; exit 0; fi
read -r TARGET STEP <<< "$SELECTION"

TARGET_DIR="$REVIEWS_DIR/$TARGET"
POLICY=$(detect_policy "$TARGET")
[ -n "$POLICY" ] && echo "-> policy: $(rel "$POLICY")" >&2
echo "" >&2

case "$STEP" in
  review)
    DEST="Codex"
    PROMPT=$(generate_review_prompt "$TARGET" "$POLICY")
    ;;
  reimplement)
    DEST="Claude Code"
    PROMPT=$(generate_reimplement_prompt "$TARGET" "$POLICY")
    ;;
  implement)
    REQ=$(ls "$TARGET_DIR"/*_requirement.md 2>/dev/null | sort | tail -1 || true)
    echo "INFO: requirement.md found. Please ask Claude Code for the initial implementation."
    echo "  -> $(rel "$REQ")"
    exit 0
    ;;
esac

echo "======================================================"
echo "  [$TARGET]"
echo "  -> prompt for $DEST"
echo "======================================================"
echo ""
echo "$PROMPT"
echo ""
echo "------------------------------------------------------"
echo "Copied to clipboard. Paste into $DEST chat."
echo "------------------------------------------------------"
echo ""

copy_clipboard "$PROMPT"