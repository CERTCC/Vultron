#!/bin/bash
# Start (or attach to) the Claude Code CLI devcontainer from the Mac terminal.
# Usage: ./start.sh [--rebuild]
set -euo pipefail

REBUILD=false
for arg in "$@"; do
    case "$arg" in
        --rebuild) REBUILD=true ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTAINER_NAME="$(basename "$SCRIPT_DIR")"
IMAGE_NAME="${CONTAINER_NAME}-image"
WORKSPACE="/workspaces/$CONTAINER_NAME"
ENV_FILE="$SCRIPT_DIR/.devcontainer/devcontainer.env"

# First-run: collect credentials
if [ ! -f "$ENV_FILE" ]; then
    bash "$SCRIPT_DIR/.devcontainer/setup.sh"
fi

# --rebuild: remove existing container and image so everything is recreated fresh
if [ "$REBUILD" = true ]; then
    echo "Rebuilding: removing container '$CONTAINER_NAME' and image '$IMAGE_NAME'..."
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rmi -f "$IMAGE_NAME" >/dev/null 2>&1 || true
fi

_exec_shell() {
    docker exec -it -u vscode -w "$WORKSPACE" \
        -e LANG=C.UTF-8 -e LC_ALL=C.UTF-8 -e TERM=xterm-256color \
        "$CONTAINER_NAME" zsh -l
}

_cleanup() {
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
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
    trap _cleanup EXIT
    docker start "$CONTAINER_NAME"
    docker exec -u vscode -w "$WORKSPACE" "$CONTAINER_NAME" \
        bash -l .devcontainer/poststart.sh
    _exec_shell
    exit 0
fi

# First create: build image, create container, run setup scripts
echo "Building image '$IMAGE_NAME'..."
docker build -t "$IMAGE_NAME" -f "$SCRIPT_DIR/docker/Dockerfile" --target dev "$SCRIPT_DIR"

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

# If this is a git worktree, the .git file points to a path on the host.
# Mount the parent .git directory at the same absolute path inside the container
# so git can resolve the worktree reference.
if [ -f "$SCRIPT_DIR/.git" ]; then
    GITDIR_REF=$(grep '^gitdir:' "$SCRIPT_DIR/.git" | sed 's/^gitdir: //')
    PARENT_GIT=$(echo "$GITDIR_REF" | sed 's|/\.git/worktrees/.*|/.git|')
    if [ -d "$PARENT_GIT" ]; then
        DOCKER_ARGS+=(-v "$PARENT_GIT:$PARENT_GIT")
    fi
fi

# Forward SSH agent if available (Docker Desktop on Mac)
if [ -S "/run/host-services/ssh-auth.sock" ]; then
    DOCKER_ARGS+=(
        -e SSH_AUTH_SOCK=/run/host-services/ssh-auth.sock
        -v /run/host-services/ssh-auth.sock:/run/host-services/ssh-auth.sock
    )
fi

docker run -d "${DOCKER_ARGS[@]}" "$IMAGE_NAME" sleep infinity
trap _cleanup EXIT

echo ""
echo "Running post-create setup (first time only)..."
docker exec -u vscode -w "$WORKSPACE" "$CONTAINER_NAME" \
    bash -l .devcontainer/postcreate.sh

echo ""
docker exec -u vscode -w "$WORKSPACE" "$CONTAINER_NAME" \
    bash -l .devcontainer/poststart.sh

_exec_shell
