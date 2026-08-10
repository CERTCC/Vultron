#!/bin/bash
# Runs on every container start/restart.
set -euo pipefail

CONTAINER_NAME="$(hostname)"

# Keep this slot's independent clone's remote-tracking refs current. Never
# touches the working tree or local branches — just a fetch.
if [ -d "$PWD/.git" ]; then
    git -C "$PWD" fetch origin --quiet 2>/dev/null || true
fi

echo ""
echo "=== $CONTAINER_NAME ==="
echo "Claude Code CLI environment ready."
echo ""
echo "  Run 'claude' to start Claude Code"
echo "  Run 'tmux' for a multiplexed terminal session"
echo ""
