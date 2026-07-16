#!/bin/bash
# Runs on every container start/restart.
set -euo pipefail

CONTAINER_NAME="$(hostname)"
echo ""
echo "=== $CONTAINER_NAME ==="
echo "Claude Code CLI environment ready."
echo ""
echo "  Run 'claude' to start Claude Code"
echo "  Run 'tmux' for a multiplexed terminal session"
echo ""
