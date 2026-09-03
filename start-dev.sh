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
BUILD_GRAPH=false

for arg in "$@"; do
    case "$arg" in
        --rebuild)     REBUILD=true ;;
        --build-graph) BUILD_GRAPH=true ;;
        --*)           echo "Unknown option: $arg"; exit 1 ;;
        *)
            if [ -n "$SLOT" ]; then
                echo "Unexpected argument: $arg"; exit 1
            fi
            SLOT="$arg"
            ;;
    esac
done

if [ "$BUILD_GRAPH" = false ] && [ -z "$SLOT" ]; then
    echo "Usage: ./start-dev.sh <slot> [--rebuild]"
    echo "       ./start-dev.sh --build-graph"
    echo ""
    echo "  slot           Name for this dev slot (e.g. inky, pinky, blinky)."
    echo "  --rebuild      Remove and rebuild the Docker image from scratch."
    echo "  --build-graph  Rebuild the ONE shared knowledge graph (from origin/main,"
    echo "                 CPU-capped) that every slot mounts read-only. Run this on"
    echo "                 demand when the graph feels stale; slots pick it up on restart."
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

# The knowledge graph is a single derived artifact of origin/main, built by ONE
# authority and mounted read-only into every slot. This dir holds that one graph.
SHARED_GRAPH="$HOME/dev/graphify-out/shared"
mkdir -p "$SHARED_GRAPH"

# --build-graph: rebuild the shared graph in a throwaway, CPU-capped container.
# This is the ONLY place graphify extraction runs — no git-hook stampede, no
# per-slot rebuilds. `graphify update .` bootstraps from empty and holds a
# per-repo lock, so re-running while a build is in flight is safe.
if [ "$BUILD_GRAPH" = true ]; then
    if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
        echo "Building image '$IMAGE_NAME'..."
        docker build -t "$IMAGE_NAME" -f "$SCRIPT_DIR/docker/Dockerfile" --target dev "$SCRIPT_DIR"
    fi

    echo "Rebuilding shared knowledge graph from origin/main (capped at ${GRAPH_BUILD_CPUS:-4} CPUs)..."
    BUILD_ARGS=(
        --rm
        --env-file "$ENV_FILE"
        --cpus "${GRAPH_BUILD_CPUS:-4}"
        --memory "${GRAPH_BUILD_MEMORY:-8g}"
        --memory-swap "${GRAPH_BUILD_MEMORY:-8g}"
        -e GRAPHIFY_MAX_WORKERS="${GRAPHIFY_MAX_WORKERS:-4}"
        -e GRAPHIFY_SKIP_HOOK=1
        -v "$SHARED_GRAPH:/app/graphify-out"
        -u vscode -w /app
    )
    if [ -f "$HOME/.gitconfig" ]; then
        BUILD_ARGS+=(-v "$HOME/.gitconfig:/home/vscode/.gitconfig:ro")
    fi
    if [ -S "/run/host-services/ssh-auth.sock" ]; then
        BUILD_ARGS+=(
            -e SSH_AUTH_SOCK=/run/host-services/ssh-auth.sock
            -v /run/host-services/ssh-auth.sock:/run/host-services/ssh-auth.sock
        )
    fi
    # Non-login shell: `bash -lc` would source /etc/profile and reset PATH to the
    # system default, dropping /app/.venv/bin. `uv run` resolves the project venv
    # regardless of PATH (uv itself lives on the system PATH), matching how every
    # Dockerfile CMD invokes project tools.
    docker run "${BUILD_ARGS[@]}" "$IMAGE_NAME" bash -c '
        set -euo pipefail
        git fetch --prune --quiet origin
        git checkout -q -f -B main origin/main
        git clean -fdq
        uv run graphify update .
    '
    echo ""
    echo "Shared graph updated at $SHARED_GRAPH"
    echo "Restart any running slots to pick it up."
    exit 0
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
    docker stop -t 5 "$CONTAINER_NAME" >/dev/null 2>&1 || true
}

# Container exists (running or stopped) — start if needed, then attach
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker start "$CONTAINER_NAME" >/dev/null 2>&1 || true
    echo "Attaching to container '$CONTAINER_NAME'..."
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
    --cpus "${SLOT_CPUS:-2}"
    --memory "${SLOT_MEMORY:-6g}"
    --memory-swap "${SLOT_MEMORY:-6g}"
    -e LANG=C.UTF-8
    -e LC_ALL=C.UTF-8
    -e TERM=xterm-256color
    -e VULTRON_MAIN_NAME="$MAIN_NAME"
    -e WIP_NOTES=/app/wip_notes
    -e WIP_OUTPUTS=/app/wip_outputs
    -e GRAPHIFY_MAX_WORKERS=4
    # Belt-and-braces: the graphify git hooks are stripped from the image (see
    # docker/Dockerfile), but this also neutralizes them if anything reinstalls
    # them inside a running slot. A slot must never rebuild the graph.
    -e GRAPHIFY_SKIP_HOOK=1
    -v "${MAIN_NAME}-data:/home/vscode/.data"
    -v "${MAIN_NAME}-${SLOT}-claude:/home/vscode/.claude"
    # NOTE: .devcontainer is NOT mounted. It is baked into the image and belongs
    # to the container's own working tree. Mounting the host copy over it made
    # one host directory the working tree for every slot plus the host repo, so
    # any git operation in one slot dirtied all the others.
    -v "$MAIN_DIR/wip_notes:/app/wip_notes:ro"
    -v "$WIP_OUTPUTS_SLOT:/app/wip_outputs"
    -w "$WORKSPACE"
)

# Knowledge graph: mount the heavy artifacts read-only from the single shared
# build. The image ships a writable, vscode-owned /app/graphify-out, so the
# query flow's disposable scratch (.vocab.txt, memory/) still writes there and
# is discarded on teardown — but graph.json is read-only, so a slot physically
# cannot rebuild or corrupt the shared graph. Mounts are added only if the graph
# exists; otherwise the slot starts graph-less and queries fall back gracefully.
if [ -f "$SHARED_GRAPH/graph.json" ]; then
    DOCKER_ARGS+=(-v "$SHARED_GRAPH/graph.json:/app/graphify-out/graph.json:ro")
    for _gf in .graphify_python manifest.json .graphify_root; do
        if [ -e "$SHARED_GRAPH/$_gf" ]; then
            DOCKER_ARGS+=(-v "$SHARED_GRAPH/$_gf:/app/graphify-out/$_gf:ro")
        fi
    done
else
    echo "NOTE: no shared graph at $SHARED_GRAPH — run './start-dev.sh --build-graph' to build it."
    echo "      This slot starts without a knowledge graph."
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
