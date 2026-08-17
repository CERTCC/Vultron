#!/bin/bash
# Runs once, when start-dev.sh CREATES a container. Re-attaching to a running
# container does not run this (start-dev.sh execs the shell directly), so the
# hard reset below can never discard an agent's work in progress.
set -euo pipefail

CONTAINER_NAME="$(hostname)"

# Force /app to origin/main. The baked .git is a copy of the host repo's, so
# without this a slot starts on whatever branch the host happened to be on at
# build time, carrying any uncommitted host edits with it.
#
# Deliberately NOT `git pull --ff-only`: pull aborts when a tracked file is
# locally modified and the incoming commits touch it, which left slots silently
# stuck on a stale snapshot. fetch + `checkout -f` cannot fail that way.
# The container is destroyed on exit, so there is no local work to protect.
if git -C /app fetch --prune --quiet origin; then
    git -C /app checkout -q -f -B main origin/main
    git -C /app clean -fdq          # no -x: keeps the gitignored CA certs and .venv
else
    echo "[error] git fetch failed — /app is the baked image snapshot, NOT origin/main"
fi

echo ""
echo "=== $CONTAINER_NAME ==="
echo "Claude Code CLI environment ready."
echo ""
echo "  Run 'claude' to start Claude Code"
echo "  Run 'tmux' for a multiplexed terminal session"
echo ""
