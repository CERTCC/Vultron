#!/bin/bash
# Start (or attach to) a slot-based Claude Code devcontainer from the Mac terminal.
# Usage: ./start-dev.sh <slot> [--rebuild] [--reset]
#   slot       Name for this dev slot (e.g. inky, pinky, main). You pick the name.
#              "main" is special: attaches to the host checkout directly.
#              Every other slot gets its own independent `git clone`, made
#              entirely inside that container — no shared git state between
#              slots, no host directory per slot.
#   --rebuild  Remove and rebuild the Docker image from scratch.
#   --reset    Wipe the slot's container (its clone goes with it). A fresh
#              clone from origin/main is made on next start.
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
    echo "             'main' attaches to the host checkout; every other slot"
    echo "             gets its own independent clone, isolated in that container."
    echo "  --rebuild  Remove and rebuild the Docker image from scratch."
    echo "  --reset    Wipe the slot's container and its clone; recreated fresh"
    echo "             from origin/main on next start."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAIN_DIR="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
MAIN_NAME="$(basename "$MAIN_DIR")"
# Strip any embedded credentials (https://user:token@host/...) before this
# ever reaches a container env var or a log line — auth should flow through
# the mounted .gitconfig's credential helper (gh, using GH_TOKEN from
# --env-file below), never through the remote URL itself.
ORIGIN_URL="$(git -C "$MAIN_DIR" remote get-url origin | sed -E 's#://[^@/]+@#://#')"
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
else
    CONTAINER_NAME="${MAIN_NAME}_${SLOT}"
    WORKSPACE="/workspaces/${MAIN_NAME}_${SLOT}"
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

# --rebuild or --reset: remove existing container first. A slot's clone lives
# entirely inside its own container's writable layer, so removing the
# container is the whole reset — there's nothing else on the host to clean up.
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

# Container exists but stopped — restart it. Its clone lives on the
# container's own writable layer and survives stop/start; only `docker rm`
# (via --reset or --rebuild) discards it.
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Starting stopped container '$CONTAINER_NAME'..."
    trap _cleanup EXIT
    docker start "$CONTAINER_NAME"
    docker exec -u vscode -w "$WORKSPACE" "$CONTAINER_NAME" \
        bash -l .devcontainer/poststart.sh
    _exec_shell
    exit 0
fi

# First create: build image (cached layers reused if unchanged), create
# container, run setup. All slots build from the main checkout's Dockerfile —
# there's no per-slot host directory anymore to source an in-progress
# Dockerfile from; test Dockerfile changes via the main checkout + --rebuild.
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
    -v "${DATA_VOLUME}:/home/vscode/.data"
    -v "$MAIN_DIR:/workspaces/${MAIN_NAME}"
    -w "$WORKSPACE"
)

# Non-main slots get their own independent `git clone`, made entirely inside
# that container's own writable filesystem layer (see .devcontainer/postcreate.sh)
# — never a host bind mount, never sharing a .git with any other slot or the
# host. Nothing any container does to its own repo (commit, branch, checkout
# someone else's PR for review, `git gc`, even `rm -rf .git`) can reach any
# other slot's repo: that's Docker's ordinary per-container filesystem
# isolation, not something enforced by careful mounting or locking.
#
# The clone is seeded from the host's main checkout via a one-time, read-only
# `--reference --dissociate`: objects are borrowed from it for speed, then
# immediately copied into the clone's own object store, so the clone has zero
# ongoing dependency on this mount or on this machine's paths once created —
# portable to any dev's machine, and safe even if the host checkout is later
# gc'd or moved.
if [ "$SLOT" != "main" ]; then
    DOCKER_ARGS+=(
        -v "$MAIN_DIR/.git:/mnt/main-repo.git:ro"
        -e VULTRON_ORIGIN_URL="$ORIGIN_URL"
    )
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

# Docker auto-creates -w's target directory as root if it doesn't already
# exist, regardless of the image's configured USER — so a non-main slot's
# fresh $WORKSPACE (never bind-mounted, unlike main's) starts out root-owned
# and the vscode user can't clone into it. Fix ownership before postcreate.sh
# (which runs as vscode) tries to.
if [ "$SLOT" != "main" ]; then
    docker exec -u root "$CONTAINER_NAME" chown vscode:vscode "$WORKSPACE"
fi

echo ""
echo "Running post-create setup (first time only)..."
docker exec -u vscode -w "$WORKSPACE" "$CONTAINER_NAME" \
    bash -l "/workspaces/${MAIN_NAME}/.devcontainer/postcreate.sh"

echo ""
docker exec -u vscode -w "$WORKSPACE" "$CONTAINER_NAME" \
    bash -l "/workspaces/${MAIN_NAME}/.devcontainer/poststart.sh"

_exec_shell
