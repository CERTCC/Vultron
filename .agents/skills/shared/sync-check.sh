#!/usr/bin/env bash
# sync-check.sh — verify the worktree is synced to origin/main.
# Exits non-zero and prints an error message if the worktree is behind.
# Usage: bash .agents/skills/shared/sync-check.sh
#
# Uses the host's manage-worktree ensure-synced when it is installed. That
# script refuses repos that keep a start-dev.sh in the main worktree; when it
# refuses for that reason, fall back to the plain fetch-and-count check.
set -euo pipefail

fallback_check() {
  if ! git fetch origin 2>/dev/null; then
    echo "❌ Aborted: could not fetch from origin." >&2
    exit 1
  fi
  BEHIND=$(git rev-list --count HEAD..origin/main)
  if [ "$BEHIND" -gt 0 ]; then
    echo "❌ Aborted: $BEHIND commit(s) behind origin/main. Run: git rebase origin/main" >&2
    exit 1
  fi
}

SCRIPT="$HOME/.copilot/skills/manage-worktree/scripts/manage_worktree.sh"
if [ -f "$SCRIPT" ]; then
  ERR=$(mktemp)
  trap 'rm -f "$ERR"' EXIT
  if bash "$SCRIPT" ensure-synced 2>"$ERR"; then
    cat "$ERR" >&2
  elif grep -q 'manages worktrees via its own start-dev.sh' "$ERR"; then
    fallback_check
  else
    cat "$ERR" >&2
    exit 1
  fi
else
  fallback_check
fi
