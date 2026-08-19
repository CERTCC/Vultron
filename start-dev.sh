#!/bin/bash
# Start (or attach to) a slot-based Claude Code devcontainer from the Mac terminal.
# Usage: ./start-dev.sh <slot> [--rebuild]
#   slot       Name for this dev slot (e.g. inky, pinky, blinky).
#              Every slot gets its own independent container. /app is baked
#              into the image, and poststart.sh force-resets it to origin/main
#              when the container is created.
#   --rebuild  Remove the image and rebuild from scratch.
set -euo pipefail

SLOT=""
REBUILD=false

for arg in "$@"; do
    case "$arg" in
        --rebuild) REBUILD=true ;;
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
    echo "Usage: ./start-dev.sh <slot> [--rebuild]"
    echo ""
    echo "  slot       Name for this dev slot (e.g. inky, pinky, blinky)."
    echo "  --rebuild  Remove and rebuild the Docker image from scratch."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAIN_DIR="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
MAIN_NAME="$(basename "$MAIN_DIR")"
IMAGE_NAME="${MAIN_NAME}-image"
ENV_FILE="$SCRIPT_DIR/.devcontainer/devcontainer.env"
CONTAINER_NAME="${MAIN_NAME}_${SLOT}"
WORKSPACE="/app"

# First-run: collect credentials
if [ ! -f "$ENV_FILE" ]; then
    bash "$SCRIPT_DIR/.devcontainer/setup.sh"
fi

# Ensure wip_notes/ and wip_outputs/ exist on the host (both gitignored)
if [ ! -d "$MAIN_DIR/wip_notes" ]; then
    mkdir -p "$MAIN_DIR/wip_notes"
    echo "Created wip_notes/ (read-only agent input). Gitignored."
fi
if [ ! -d "$MAIN_DIR/wip_outputs" ]; then
    mkdir -p "$MAIN_DIR/wip_outputs"
    echo "Created wip_outputs/ (agent output files). Gitignored."
fi
mkdir -p "$MAIN_DIR/wip_outputs/$SLOT"
WIP_OUTPUTS_SLOT="$MAIN_DIR/wip_outputs/$SLOT"

# Ensure per-slot graphify-out dir exists on the host
GRAPHIFY_HOST="$HOME/dev/graphify-out/$SLOT"
mkdir -p "$GRAPHIFY_HOST"

# --rebuild: remove container and image
if [ "$REBUILD" = true ]; then
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Removing container '$CONTAINER_NAME'..."
        docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    fi
    echo "Removing image '$IMAGE_NAME'..."
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

# Build image (cached layers reused if unchanged)
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
    -e VULTRON_MAIN_NAME="$MAIN_NAME"
    -e WIP_NOTES=/app/wip_notes
    -e WIP_OUTPUTS=/app/wip_outputs
    -v "${MAIN_NAME}-data:/home/vscode/.data"
    # NOTE: .devcontainer is NOT mounted. It is baked into the image and belongs
    # to the container's own working tree. Mounting the host copy over it made
    # one host directory the working tree for every slot plus the host repo, so
    # any git operation in one slot dirtied all the others.
    -v "$MAIN_DIR/wip_notes:/app/wip_notes:ro"
    -v "$WIP_OUTPUTS_SLOT:/app/wip_outputs"
    -v "$GRAPHIFY_HOST:/app/graphify-out"
    -w "$WORKSPACE"
)

# Mount clipboard bridge socket if the host listener is running (see scripts/clipboard-bridge.sh)
if [ -S "/tmp/docker-clipboard.sock" ]; then
    DOCKER_ARGS+=(-v /tmp/docker-clipboard.sock:/tmp/clipboard.sock)
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

docker run -d "${DOCKER_ARGS[@]}" "$IMAGE_NAME" sleep infinity
trap _cleanup EXIT

echo ""
echo "Running post-create setup (first time only)..."
docker exec -u vscode -w "$WORKSPACE" "$CONTAINER_NAME" \
    bash -l /app/.devcontainer/postcreate.sh

echo ""
docker exec -u vscode -w "$WORKSPACE" "$CONTAINER_NAME" \
    bash -l /app/.devcontainer/poststart.sh

_exec_shell
