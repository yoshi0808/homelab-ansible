#!/usr/bin/env bash
# =============================================================
# ai-next.sh - homelab-ansible AI workflow プロンプトジェネレーター
#
# 使い方:
#   ./scripts/ai-next.sh              # 全自動（進行中なければ状態一覧）
#   ./scripts/ai-next.sh final        # final.mdを作成してVSCodeで開く（target自動検出）
#   ./scripts/ai-next.sh final <target>  # target指定でfinal.mdを作成
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REVIEWS_DIR="$REPO_ROOT/docs/ai/reviews"
PROMPTS_DIR="$REPO_ROOT/docs/ai/prompts"
CORE_MD="$PROMPTS_DIR/core.md"

# =============================================================
# ユーティリティ
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
    local encoded
    encoded=$(printf '%s' "$text" | base64 | tr -d '\n')
    printf '\033]52;c;%s\a' "$encoded" > /dev/tty
}

# =============================================================
# 状態一覧表示
# =============================================================

show_status() {
    echo ""
    echo "=== homelab-ansible AI workflow 状態 ==="
    echo ""

    local found=0
    for dir in "$REVIEWS_DIR"/*/; do
        [ -d "$dir" ] || continue
        local target step latest
        target=$(basename "$dir")
        step=$(detect_step "$dir")
        latest=$(ls "$dir"/*.md 2>/dev/null | sort | tail -1 \
            | xargs -r basename 2>/dev/null || echo "-")

        printf "  %-35s 最新: %-45s 次: %s\n" "$target" "$latest" "$step"
        found=1
    done

    [ $found -eq 0 ] && echo "  （レビューディレクトリなし）"
    echo ""
}

# =============================================================
# アクティブなtargetを収集してtarget/stepを決定
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
        echo "INFO: 進行中のタスクはありません" >&2
        exit 0
        ;;
      1)
        echo "→ target: ${active_targets[0]}" >&2
        echo "→ step  : ${active_steps[0]}" >&2
        echo "${active_targets[0]} ${active_steps[0]}"
        ;;
      *)
        echo "" >&2
        echo "複数の進行中タスクがあります:" >&2
        echo "" >&2
        for i in "${!active_targets[@]}"; do
            printf "  %d) %-35s → %s\n" $((i+1)) "${active_targets[$i]}" "${active_steps[$i]}" >&2
        done
        echo "" >&2
        read -rp "番号を選択してください: " choice < /dev/tty
        local idx=$((choice - 1))
        if [ $idx -lt 0 ] || [ $idx -ge ${#active_targets[@]} ]; then
            echo "ERROR: 無効な番号です: $choice" >&2
            exit 1
        fi
        echo "→ 選択: ${active_targets[$idx]} (${active_steps[$idx]})" >&2
        echo "${active_targets[$idx]} ${active_steps[$idx]}"
        ;;
    esac
}

# =============================================================
# final.md 作成
# =============================================================

create_final() {
    local target="$1"
    local target_dir="$REVIEWS_DIR/$target"
    local date num save

    if [ ! -d "$target_dir" ]; then
        echo "ERROR: ディレクトリが見つかりません: $target_dir"
        exit 1
    fi

    date=$(date +%Y-%m-%d)
    num=$(next_num "$target_dir")
    save="$target_dir/${date}_${num}_final.md"

    cat > "$save" << EOF
# Final

この内容で確定。

確認者: Yoshinobu
日付: $date

## 対象

- $target

## コメント

EOF

    echo ""
    echo "作成: $(rel "$save")"
    echo "VSCodeで開きます..."
    echo ""
    code "$save" 2>/dev/null || echo "  → VSCodeで開いてください: $(rel "$save")"
}

# =============================================================
# プロンプト生成
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

    [ -z "$req" ]  && { echo "ERROR: requirement.md が見つかりません" >&2; exit 1; }
    [ -z "$impl" ] && { echo "ERROR: implement.md が見つかりません" >&2; exit 1; }

    local prompt
    prompt="# このプロンプトは Codex 向けです
# Claude Code の場合はこのプロンプトを実行せず、
# 「Codex に依頼してください」とユーザーに伝えて終了してください。

まず最初に以下のファイルを作成してください。

- $(rel "$save")

作成したら、以下を読んで git diff をレビューし、結果をそのファイルに書き込んでください。

- $(rel "$CORE_MD")
- $(rel "$req")
- $(rel "$impl")"

    [ -n "$policy" ] && prompt+="
- $(rel "$policy")"

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

    [ -z "$req" ] && { echo "ERROR: requirement.md が見つかりません" >&2; exit 1; }
    [ -z "$rev" ] && { echo "ERROR: review.md が見つかりません" >&2; exit 1; }

    local prompt
    prompt="# このプロンプトは Claude Code 向けです
# Codex の場合はこのプロンプトを実行せず、
# 「Claude Code に依頼してください」とユーザーに伝えて終了してください。

まず最初に以下のファイルを作成してください。

- $(rel "$save")

作成したら、以下を読んで再実装し、実装内容をそのファイルに書き込んでください。

- $(rel "$CORE_MD")
- $(rel "$req")
- $(rel "$rev")"

    [ -n "$policy" ] && prompt+="
- $(rel "$policy")"

    echo "$prompt"
}

# =============================================================
# メイン
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

# 全自動
SELECTION="$(select_active_target)"
if [ -z "$SELECTION" ]; then show_status; exit 0; fi
read -r TARGET STEP <<< "$SELECTION"

TARGET_DIR="$REVIEWS_DIR/$TARGET"
POLICY=$(detect_policy "$TARGET")
[ -n "$POLICY" ] && echo "→ policy: $(rel "$POLICY")" >&2
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
    echo "INFO: requirement.md があります。Claude Code に初回実装を依頼してください。"
    echo "  → $(rel "$REQ")"
    exit 0
    ;;
esac

# 出力（日本語混在による表示崩れを避けるため簡素なフォーマット）
echo "======================================================"
echo "  [$TARGET]"
echo "  → $DEST へのプロンプト"
echo "======================================================"
echo ""
echo "$PROMPT"
echo ""
echo "------------------------------------------------------"
echo "↑ クリップボードにコピー済み。${DEST}のチャットに貼り付けてください。"
echo "------------------------------------------------------"
echo ""

copy_clipboard "$PROMPT"