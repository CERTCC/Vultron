#!/bin/bash
# Start (or attach to) the Claude Code CLI devcontainer from the Mac terminal.
# Usage: ./start.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTAINER_NAME="$(basename "$SCRIPT_DIR")"
IMAGE_NAME="${CONTAINER_NAME}-image"
WORKSPACE="/workspaces/$CONTAINER_NAME"
ENV_FILE="$SCRIPT_DIR/.devcontainer/devcontainer.env"

# First-run: collect credentials
if [ ! -f "$ENV_FILE" ]; then
    bash "$SCRIPT_DIR/.devcontainer/setup.sh"
fi

_exec_shell() {
    docker exec -it -u vscode -w "$WORKSPACE" \
        -e LANG=C.UTF-8 -e LC_ALL=C.UTF-8 -e TERM=xterm-256color \
        "$CONTAINER_NAME" zsh -l
}

# Container already running — just attach
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Attaching to running container '$CONTAINER_NAME'..."
    _exec_shell
    exit 0
fi

# Container exists but stopped — restart it
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Starting stopped container '$CONTAINER_NAME'..."
    docker start "$CONTAINER_NAME"
    docker exec -u vscode -w "$WORKSPACE" "$CONTAINER_NAME" \
        bash -l .devcontainer/poststart.sh
    _exec_shell
    exit 0
fi

# First create: build image, create container, run setup scripts
echo "Building image '$IMAGE_NAME'..."
docker build -t "$IMAGE_NAME" "$SCRIPT_DIR/.devcontainer"

echo ""
echo "Creating container '$CONTAINER_NAME'..."
DOCKER_ARGS=(
    --name "$CONTAINER_NAME"
    --hostname "$CONTAINER_NAME"
    --env-file "$ENV_FILE"
    -e LANG=C.UTF-8
    -e LC_ALL=C.UTF-8
    -e TERM=xterm-256color
    -v "${CONTAINER_NAME}-data:/home/vscode/.data"
    -v "$SCRIPT_DIR:$WORKSPACE"
    -w "$WORKSPACE"
)

# Forward SSH agent if available (Docker Desktop on Mac)
if [ -S "/run/host-services/ssh-auth.sock" ]; then
    DOCKER_ARGS+=(
        -e SSH_AUTH_SOCK=/run/host-services/ssh-auth.sock
        -v /run/host-services/ssh-auth.sock:/run/host-services/ssh-auth.sock
    )
fi

docker run -d "${DOCKER_ARGS[@]}" "$IMAGE_NAME" sleep infinity

echo ""
echo "Running post-create setup (first time only)..."
docker exec -u vscode -w "$WORKSPACE" "$CONTAINER_NAME" \
    bash -l .devcontainer/postcreate.sh

echo ""
docker exec -u vscode -w "$WORKSPACE" "$CONTAINER_NAME" \
    bash -l .devcontainer/poststart.sh

_exec_shell
