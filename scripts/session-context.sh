#!/usr/bin/env bash
# SessionStart hook: /clear・再起動・compactのたびに「現在地」を文脈へ載せる。
#
# 規範(どう振る舞うか)は CLAUDE.md → docs/ai/core.md が入口として既に機能している。
# ここで補うのは状態(今どこにいて何を待っているか)であり、その正本は docs/ai/status.md。
# 要約せず現物を渡す — 要約した層は必ず本文より古くなる
# (docs/ai/memory/lessons/always-loaded-summaries-are-the-least-current.md)。
#
# セッション起動を妨げないことを最優先とし、何が失敗しても exit 0 で抜ける。
set -uo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)" || exit 0
cd "$repo" 2>/dev/null || exit 0

body="$(
  {
    echo "# セッション開始時の現在地(SessionStart hook: scripts/session-context.sh)"
    echo
    echo "## docs/ai/status.md(状態の正本)"
    echo
    if [ -r docs/ai/status.md ]; then
      cat docs/ai/status.md
    else
      echo "(docs/ai/status.md が読めない。存在しないなら状態の正本が失われているので確認すること)"
    fi
    echo
    echo "## git status --short(未commitの現物)"
    echo
    git status --short 2>/dev/null | head -40 || true
    echo
    echo "## 直近のcommit"
    echo
    git log --oneline -5 2>/dev/null || true
  } 2>/dev/null
)"

if command -v jq >/dev/null 2>&1; then
  jq -n --arg ctx "$body" \
    '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$ctx},suppressOutput:true}' \
    2>/dev/null || printf '%s\n' "$body"
else
  printf '%s\n' "$body"
fi

exit 0
