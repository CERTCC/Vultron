#!/usr/bin/env bash
# sync-check.sh — verify the worktree is synced to origin/main.
# Exits non-zero and prints an error message if the worktree is behind.
# Usage: bash .agents/skills/shared/sync-check.sh
set -euo pipefail

SCRIPT="$HOME/.copilot/skills/manage-worktree/scripts/manage_worktree.sh"
if [ -f "$SCRIPT" ]; then
  bash "$SCRIPT" ensure-synced
else
  if ! git fetch origin 2>/dev/null; then
    echo "❌ Aborted: could not fetch from origin." >&2
    exit 1
  fi
  BEHIND=$(git rev-list --count HEAD..origin/main)
  if [ "$BEHIND" -gt 0 ]; then
    echo "❌ Aborted: $BEHIND commit(s) behind origin/main. Run: git rebase origin/main" >&2
    exit 1
  fi
fi
