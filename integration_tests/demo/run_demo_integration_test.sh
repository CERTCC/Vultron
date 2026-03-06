#!/usr/bin/env bash
# Integration test for the unified Vultron demo CLI (DC-06-001).
#
# Starts the api-dev service, waits for it to be healthy, then runs
# `vultron-demo all` inside the demo container and verifies all demos
# complete without errors.
#
# Usage:
#   ./integration_tests/demo/run_demo_integration_test.sh
#
# Prerequisites: Docker and docker compose available on PATH.
# Run from the repository root.
#
# Exit codes:
#   0 - all demos passed
#   1 - one or more demos failed or the API failed to become healthy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker/docker-compose.yml"
PROJECT_NAME="${PROJECT_NAME:-vultron}"

log() { echo "[integration-test] $*"; }
fail() { log "FAIL: $*"; exit 1; }

cleanup() {
    log "Stopping containers..."
    docker compose -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" \
        stop api-dev demo 2>/dev/null || true
}
trap cleanup EXIT

# Build images if needed, then start api-dev in the background.
log "Building images..."
docker compose -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" build api-dev demo

log "Starting api-dev..."
docker compose -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" up -d api-dev

# Wait for api-dev to pass its health check (up to 60 s).
log "Waiting for api-dev to become healthy..."
MAX_WAIT=60
ELAPSED=0
until docker compose -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" \
        ps api-dev | grep -q "healthy"; do
    if [ "${ELAPSED}" -ge "${MAX_WAIT}" ]; then
        fail "api-dev did not become healthy within ${MAX_WAIT}s"
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done
log "api-dev is healthy."

# Run vultron-demo all inside the demo container and capture exit code.
log "Running vultron-demo all inside the demo container..."
docker compose -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" \
    run --rm -e DEMO=all demo \
    && DEMO_EXIT=0 || DEMO_EXIT=$?

if [ "${DEMO_EXIT}" -ne 0 ]; then
    fail "vultron-demo all exited with status ${DEMO_EXIT}"
fi

log "SUCCESS: all demos passed."
