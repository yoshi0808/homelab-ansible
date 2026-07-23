#!/usr/bin/env bash
# Local helper (gitignored). Starts/attaches the `homelab` tmux session with a
# fixed 2x2 pane grid:
#   top-left     = claude       (Claude Code, requirement/hub — talks to the
#                  user, owns requirement/implement/review handoffs, monitor
#                  mode auto-receive)
#   top-right    = reviewer     (Codex, on the agmsg monitor bridge — auto-receive)
#   bottom-left  = implementer  (Codex, kick-based — implementation only,
#                  receives requirement/review from claude via agmsg, never
#                  talks to reviewer/tester directly)
#   bottom-right = tester       (Codex, kick-based)
#
#   Window 1 "workers" = implementer2 (left) + tester2 (right) (Codex,
#                  kick-based — 2nd implementer + 2nd tester; claude picks
#                  among the two implementers / two testers by task volume)
#
# Every Codex agent (reviewer / implementer / tester / implementer2) is
# kick-based: agmsg's 1-codex-per-project monitor bridge is held by reviewer and
# in practice even it is kicked by claude, so each codex launches as plain codex
# (agmsg shim stripped from $NOSHIM_PATH) and receives via kick. claude
# (top-left, Claude Code) is the only monitor-auto-receive agent. All non-claude
# agents are spawned + bootstrapped (read core.md) in parallel with claude's
# startup. Two codex implementers since 2026-07-14 (was 1 Claude-Code
# implementer + no window 1).
#
# Usage:
#   ./new-session.sh            # create (or attach to) the session
#   ./new-session.sh --pane0    # INTERNAL: pane-0 boot command (do not run by hand)
set -euo pipefail

SESSION=homelab
DIR=/home/yoshi/homelab-ansible
AGMSG=/home/yoshi/.agents/skills/agmsg/scripts
HERE="$(cd "$(dirname "$0")" && pwd)"
SELF="$HERE/$(basename "$0")"

# --- pane-0 boot mode: runs INSIDE tmux as pane 0's command -----------------
if [ "${1:-}" = "--pane0" ]; then
  A="$(tmux display-message -p '#{pane_id}')"

  # Bottom-left: will become implementer (below). Split A top/bottom first so
  # subsequent splits of A (for reviewer) only affect the top half, giving a
  # clean 2x2 grid.
  tmux split-window -v -t "$A"
  D="$(tmux list-panes -t "$SESSION:0" -F '#{pane_id}' | tail -1)"

  # Top-right: reviewer, spawned by splitting A (top-left) horizontally.
  tmux select-pane -t "$A"
  before="$(tmux list-panes -t "$SESSION" -F '#{pane_id}' | sort)"
  "$AGMSG/spawn.sh" codex reviewer --team "$SESSION" --split h --no-wait || true
  after="$(tmux list-panes -t "$SESSION" -F '#{pane_id}' | sort)"
  reviewer_pane="$(comm -13 <(printf '%s\n' "$before") <(printf '%s\n' "$after") | head -1 || true)"
  if [ -n "$reviewer_pane" ]; then
    "$HERE/prep-agent.sh" "$reviewer_pane" reviewer codex >/tmp/prep-reviewer.log 2>&1 &
  else
    echo "new-session: could not resolve reviewer pane; skipping bootstrap" >&2
  fi

  # Bottom-right: tester, spawned by splitting D (bottom-left) horizontally.
  # Strip the agmsg shim from PATH for this spawn only (see start-tester.sh's
  # old comment / reference_codex_agmsg_kick memory): the monitor bridge only
  # serves one codex per project, reviewer already holds it, so tester must
  # launch as plain codex and receive via kick instead.
  tmux select-pane -t "$D"
  NOSHIM_PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -vxF "$HOME/.agents/bin" | paste -sd: || true)"
  before2="$(tmux list-panes -t "$SESSION" -F '#{pane_id}' | sort)"
  PATH="$NOSHIM_PATH" "$AGMSG/spawn.sh" codex tester --team "$SESSION" --split h --no-wait || true
  after2="$(tmux list-panes -t "$SESSION" -F '#{pane_id}' | sort)"
  tester_pane="$(comm -13 <(printf '%s\n' "$before2") <(printf '%s\n' "$after2") | head -1 || true)"
  if [ -n "$tester_pane" ]; then
    "$HERE/prep-agent.sh" "$tester_pane" tester codex >/tmp/prep-tester.log 2>&1 &
  else
    echo "new-session: could not resolve tester pane; skipping bootstrap" >&2
  fi

  # Bottom-left: implementer (Codex, kick-based), in place — respawn D directly
  # with a plain-codex actas launch (agmsg shim stripped via $NOSHIM_PATH, same
  # reason as tester: only one codex rides the monitor bridge and reviewer holds
  # it). Pre-join first (join.sh) so the actas claim doesn't hit an interactive
  # team prompt. codex takes the actas prompt as a positional arg and
  # auto-submits it. Backgrounded so it doesn't delay the final `exec claude`.
  (
    AGMSG_RESOLVE_PROJECT=0 "$AGMSG/join.sh" "$SESSION" implementer codex "$DIR" >/dev/null 2>&1 || true
    tmux respawn-pane -k -t "$D" "PATH=$NOSHIM_PATH codex '/agmsg actas implementer'; exec bash -i"
    "$HERE/prep-agent.sh" "$D" implementer codex
  ) >/tmp/prep-implementer.log 2>&1 &

  # Window 1 (name "workers"): implementer2 (left) + tester2 (right), both
  # kick-based Codex. The 2x2 grid on window 0 is full, so the two "second"
  # workers share window 1 side by side. 2 implementers (implementer +
  # implementer2) and 2 testers (tester + tester2) since 2026-07-20; claude
  # picks by task volume / parallelism.
  (
    AGMSG_RESOLVE_PROJECT=0 "$AGMSG/join.sh" "$SESSION" implementer2 codex "$DIR" >/dev/null 2>&1 || true
    tmux new-window -d -t "$SESSION" -n workers -c "$DIR"
    i2_pane="$(tmux list-panes -t "$SESSION:workers" -F '#{pane_id}' | head -1)"
    tmux respawn-pane -k -t "$i2_pane" "PATH=$NOSHIM_PATH codex '/agmsg actas implementer2'; exec bash -i"
    "$HERE/prep-agent.sh" "$i2_pane" implementer2 codex
    # tester2 beside implementer2 on the same window (2nd tester, kick-based).
    AGMSG_RESOLVE_PROJECT=0 "$AGMSG/join.sh" "$SESSION" tester2 codex "$DIR" >/dev/null 2>&1 || true
    before_t2="$(tmux list-panes -t "$SESSION:workers" -F '#{pane_id}' | sort)"
    tmux split-window -h -t "$i2_pane" -c "$DIR"
    after_t2="$(tmux list-panes -t "$SESSION:workers" -F '#{pane_id}' | sort)"
    t2_pane="$(comm -13 <(printf '%s\n' "$before_t2") <(printf '%s\n' "$after_t2") | head -1)"
    tmux respawn-pane -k -t "$t2_pane" "PATH=$NOSHIM_PATH codex '/agmsg actas tester2'; exec bash -i"
    "$HERE/prep-agent.sh" "$t2_pane" tester2 codex
  ) >/tmp/prep-workers.log 2>&1 &

  # Even out the right column (split percentages can drift slightly across
  # the two splits above) and hand focus back to claude.
  tmux select-pane -t "$A"
  exec claude
fi

# --- normal mode: run from your shell ---------------------------------------
if tmux has-session -t "$SESSION" 2>/dev/null; then
  exec tmux attach -t "$SESSION"
fi

tmux new-session -d -s "$SESSION" -c "$DIR" "$SELF --pane0"
exec tmux attach -t "$SESSION"
