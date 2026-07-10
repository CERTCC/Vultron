#!/bin/bash
# Start (or attach to) a slot-based Claude Code devcontainer from the Mac terminal.
# Usage: ./start-dev.sh <slot> [--rebuild] [--reset]
#   slot       Name for this dev slot (e.g. inky, pinky, main). You pick the name.
#              "main" is special: attaches to the main checkout with no worktree.
#   --rebuild  Remove and rebuild the Docker image from scratch.
#   --reset    Delete the slot's worktree and recreate it from main (also removes container).
set -euo pipefail

SLOT=""
REBUILD=false
RESET=false

for arg in "$@"; do
    case "$arg" in
        --rebuild) REBUILD=true ;;
        --reset)   RESET=true ;;
        --*)       echo "Unknown option: $arg"; exit 1 ;;
        *)
            if [ -n "$SLOT" ]; then
                echo "Unexpected argument: $arg"; exit 1
            fi
            SLOT="$arg"
            ;;
    esac
done

if [ -z "$SLOT" ]; then
    echo "Usage: ./start-dev.sh <slot> [--rebuild] [--reset]"
    echo ""
    echo "  slot       Name for this dev slot (e.g. inky, pinky, main)."
    echo "             'main' attaches to the main checkout; all others create a worktree."
    echo "  --rebuild  Remove and rebuild the Docker image from scratch."
    echo "  --reset    Delete the slot's worktree and recreate it from main."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAIN_DIR="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
PARENT_DIR="$(dirname "$MAIN_DIR")"
MAIN_NAME="$(basename "$MAIN_DIR")"
IMAGE_NAME="${MAIN_NAME}-image"
DATA_VOLUME="${MAIN_NAME}-data"
ENV_FILE="$SCRIPT_DIR/.devcontainer/devcontainer.env"

# First-run: collect credentials
if [ ! -f "$ENV_FILE" ]; then
    bash "$SCRIPT_DIR/.devcontainer/setup.sh"
fi

if [ "$SLOT" = "main" ]; then
    CONTAINER_NAME="${MAIN_NAME}_main"
    WORKSPACE="/workspaces/${MAIN_NAME}"
    WORKTREE_PATH="$MAIN_DIR"
else
    CONTAINER_NAME="${MAIN_NAME}_${SLOT}"
    WORKSPACE="/workspaces/${MAIN_NAME}_${SLOT}"
    WORKTREE_PATH="${PARENT_DIR}/${MAIN_NAME}_${SLOT}"
fi

# Ensure wip_notes/ and wip_outputs/ exist on the host (both gitignored)
_created_wip=false
if [ ! -d "$MAIN_DIR/wip_notes" ]; then
    mkdir -p "$MAIN_DIR/wip_notes"
    _created_wip=true
fi
if [ ! -d "$MAIN_DIR/wip_outputs" ]; then
    mkdir -p "$MAIN_DIR/wip_outputs"
    _created_wip=true
fi
if [ "$_created_wip" = true ]; then
    echo "Created wip_notes/ (read-only agent input) and/or wip_outputs/ (agent output files). Both are gitignored."
fi
mkdir -p "$MAIN_DIR/wip_outputs/$SLOT"

# --rebuild or --reset: remove existing container first
if [ "$REBUILD" = true ] || [ "$RESET" = true ]; then
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Removing container '$CONTAINER_NAME'..."
        docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    fi
fi

# --rebuild: also remove the image
if [ "$REBUILD" = true ]; then
    echo "Removing image '$IMAGE_NAME'..."
    docker rmi -f "$IMAGE_NAME" >/dev/null 2>&1 || true
fi

# Worktree management (non-main slots only)
if [ "$SLOT" != "main" ]; then
    if [ "$RESET" = true ] && [ -d "$WORKTREE_PATH" ]; then
        echo "Resetting worktree at '$WORKTREE_PATH'..."
        git -C "$MAIN_DIR" worktree remove --force "$WORKTREE_PATH"
    fi
    if [ ! -d "$WORKTREE_PATH" ]; then
        echo "Creating worktree at '$WORKTREE_PATH'..."
        git -C "$MAIN_DIR" worktree add --detach "$WORKTREE_PATH"
    fi
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

# First create: build image (cached layers reused if unchanged), create container, run setup
# Use the worktree's Dockerfile for non-main slots so in-progress Dockerfile changes are picked up.
if [ "$SLOT" = "main" ]; then
    DOCKERFILE="$SCRIPT_DIR/docker/Dockerfile"
else
    DOCKERFILE="$WORKTREE_PATH/docker/Dockerfile"
fi
echo "Building image '$IMAGE_NAME'..."
docker build -t "$IMAGE_NAME" -f "$DOCKERFILE" --target dev "$SCRIPT_DIR"

echo ""
echo "Creating container '$CONTAINER_NAME'..."
DOCKER_ARGS=(
    --name "$CONTAINER_NAME"
    --hostname "$CONTAINER_NAME"
    --env-file "$ENV_FILE"
    -e LANG=C.UTF-8
    -e LC_ALL=C.UTF-8
    -e TERM=xterm-256color
    -e VULTRON_MAIN_NAME="$MAIN_NAME"
    -v "${DATA_VOLUME}:/home/vscode/.data"
    -v "$MAIN_DIR:/workspaces/${MAIN_NAME}"
    -w "$WORKSPACE"
)

# Mount slot worktree and parent .git for worktree ref resolution (non-main slots only)
if [ "$SLOT" != "main" ]; then
    DOCKER_ARGS+=(-v "$WORKTREE_PATH:$WORKSPACE")
    # Mount parent .git at its absolute host path so worktree gitdir references resolve inside container
    DOCKER_ARGS+=(-v "$MAIN_DIR/.git:$MAIN_DIR/.git")
fi

# Mount user-level skills read-only if present on the host
if [ -d "$HOME/.agents/skills" ]; then
    DOCKER_ARGS+=(-v "$HOME/.agents/skills:/home/vscode/.agents/skills:ro")
fi

# Mount host .gitconfig so commits use the user's real identity
if [ -f "$HOME/.gitconfig" ]; then
    DOCKER_ARGS+=(-v "$HOME/.gitconfig:/home/vscode/.gitconfig:ro")
fi

# Forward SSH agent if available (Docker Desktop on Mac)
if [ -S "/run/host-services/ssh-auth.sock" ]; then
    DOCKER_ARGS+=(
        -e SSH_AUTH_SOCK=/run/host-services/ssh-auth.sock
        -v /run/host-services/ssh-auth.sock:/run/host-services/ssh-auth.sock
    )
fi

# Mount wip_notes (read-only) and wip_outputs (read-write, namespaced by slot)
DOCKER_ARGS+=(
    -v "$MAIN_DIR/wip_notes:/workspaces/wip_notes:ro"
    -v "$MAIN_DIR/wip_outputs:/workspaces/wip_outputs"
    -e WIP_NOTES=/workspaces/wip_notes
    -e WIP_OUTPUTS=/workspaces/wip_outputs/$SLOT
)

docker run -d "${DOCKER_ARGS[@]}" "$IMAGE_NAME" sleep infinity
trap _cleanup EXIT

echo ""
echo "Running post-create setup (first time only)..."
docker exec -u vscode -w "$WORKSPACE" "$CONTAINER_NAME" \
    bash -l "/workspaces/${MAIN_NAME}/.devcontainer/postcreate.sh"

echo ""
docker exec -u vscode -w "$WORKSPACE" "$CONTAINER_NAME" \
    bash -l "/workspaces/${MAIN_NAME}/.devcontainer/poststart.sh"

_exec_shell
