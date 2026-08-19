#!/bin/bash
# Run this on your Mac before starting a dev container.
# It listens on a Unix socket and pipes incoming data to pbcopy, so that
# mouse-drag selections inside tmux in the container land on your Mac clipboard.
#
# Usage: ./scripts/clipboard-bridge.sh
#   Keep it running in a terminal tab, or wire it into your login items.
#
# start-dev.sh mounts the socket into the container automatically when it exists.
set -euo pipefail

SOCK=/tmp/docker-clipboard.sock

cleanup() { rm -f "$SOCK"; }
trap cleanup EXIT INT TERM

rm -f "$SOCK"
echo "Clipboard bridge listening on $SOCK — keep this running while using dev containers."

while true; do
    nc -lU "$SOCK" | pbcopy
done
