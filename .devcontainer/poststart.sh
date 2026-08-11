#!/bin/bash
# Runs on every container start.
set -euo pipefail

CONTAINER_NAME="$(hostname)"

# Refresh /app from origin. The container is ephemeral (destroyed on exit),
# so there are never local uncommitted changes to protect here.
git -C /app pull --ff-only --quiet 2>&1 || echo "[warn] git pull failed — running with baked image snapshot"

echo ""
echo "=== $CONTAINER_NAME ==="
echo "Claude Code CLI environment ready."
echo ""
echo "  Run 'claude' to start Claude Code"
echo "  Run 'tmux' for a multiplexed terminal session"
echo ""
