#!/usr/bin/env bash
# Integration test for multi-actor Vultron demo scenarios (D5-5).
#
# Satisfies DEMO-MA-03-001: each scenario is runnable via a single command.
#
# Starts all actor services defined in docker-compose-multi-actor.yml, waits
# for every actor to pass its /health/ready health check (DEMO-MA-02-001),
# runs the selected scenario via the demo-runner service, and reports the
# outcome.
#
# Usage:
#   ./integration_tests/demo/run_multi_actor_integration_test.sh [SCENARIO]
#
#   SCENARIO   One of: two-actor (default), three-actor, multi-vendor
#
# Environment variables:
#   DEMO                  Alternative way to specify the scenario (overridden by
#                         the positional argument when both are supplied).
#   PROJECT_NAME          Docker resource name prefix (default: vultron-it).
#                         Use a unique prefix to avoid conflicts with a running
#                         development stack.
#   FINDER_HOST_PORT      Host port for the finder service (default: 7901).
#   VENDOR_HOST_PORT      Host port for the vendor service (default: 7902).
#   CASE_ACTOR_HOST_PORT  Host port for the case-actor service (default: 7903).
#   COORDINATOR_HOST_PORT Host port for the coordinator service (default: 7904).
#   VENDOR2_HOST_PORT     Host port for the vendor2 service (default: 7905).
#
#   Override port env vars when the defaults conflict with a running stack:
#     FINDER_HOST_PORT=17901 VENDOR_HOST_PORT=17902 ... \
#       ./integration_tests/demo/run_multi_actor_integration_test.sh
#
# Exit codes:
#   0   Scenario completed successfully.
#   1   Build failure, health-check timeout, or scenario failure.
#
# Prerequisites: Docker and docker compose available on PATH.
# Run from the repository root.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker/docker-compose-multi-actor.yml"
PROJECT_NAME="${PROJECT_NAME:-vultron-it}"
DEMO="${1:-${DEMO:-two-actor}}"

VALID_SCENARIOS="two-actor three-actor multi-vendor"
if ! echo "${VALID_SCENARIOS}" | grep -qw "${DEMO}"; then
    echo "ERROR: unknown scenario '${DEMO}'. Valid options: ${VALID_SCENARIOS}" >&2
    exit 1
fi

log()  { echo "[multi-actor-integration] $*"; }
fail() { log "FAIL: $*"; exit 1; }

# Check whether a TCP port is already bound on the host.
# Returns 0 (busy) or 1 (free).
port_busy() {
    local port="$1"
    # Use nc -z if available; fall back to /dev/tcp.
    if command -v nc >/dev/null 2>&1; then
        nc -z 127.0.0.1 "${port}" 2>/dev/null
    else
        (echo >/dev/tcp/127.0.0.1/"${port}") 2>/dev/null
    fi
}

# Resolve the effective host port for each service (respecting env-var overrides).
FINDER_HOST_PORT="${FINDER_HOST_PORT:-7901}"
VENDOR_HOST_PORT="${VENDOR_HOST_PORT:-7902}"
CASE_ACTOR_HOST_PORT="${CASE_ACTOR_HOST_PORT:-7903}"
COORDINATOR_HOST_PORT="${COORDINATOR_HOST_PORT:-7904}"
VENDOR2_HOST_PORT="${VENDOR2_HOST_PORT:-7905}"

# Pre-flight: check that none of the required host ports are already bound.
# Binding conflicts produce an opaque Docker networking error; checking early
# gives a clear, actionable message and avoids partial-stack startup.
CONFLICTING_PORTS=()
for port_var in FINDER_HOST_PORT VENDOR_HOST_PORT CASE_ACTOR_HOST_PORT \
                COORDINATOR_HOST_PORT VENDOR2_HOST_PORT; do
    port="${!port_var}"
    if port_busy "${port}"; then
        CONFLICTING_PORTS+=("${port} (${port_var})")
    fi
done

if [ "${#CONFLICTING_PORTS[@]}" -gt 0 ]; then
    log "ERROR: the following host ports are already in use:"
    for entry in "${CONFLICTING_PORTS[@]}"; do
        log "  - ${entry}"
    done
    log "Override with env vars to use different host ports, e.g.:"
    log "  FINDER_HOST_PORT=17901 VENDOR_HOST_PORT=17902 \\"
    log "  CASE_ACTOR_HOST_PORT=17903 COORDINATOR_HOST_PORT=17904 \\"
    log "  VENDOR2_HOST_PORT=17905 \\"
    log "  ${BASH_SOURCE[0]} ${DEMO}"
    fail "Port conflict detected; aborting before Docker startup."
fi

cleanup() {
    log "Removing containers and volumes..."
    docker compose \
        -f "${COMPOSE_FILE}" \
        -p "${PROJECT_NAME}" \
        down --volumes --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

log "Scenario : ${DEMO}"
log "Project  : ${PROJECT_NAME}"
log "Compose  : ${COMPOSE_FILE}"
log "Ports    : finder=${FINDER_HOST_PORT} vendor=${VENDOR_HOST_PORT} case-actor=${CASE_ACTOR_HOST_PORT} coordinator=${COORDINATOR_HOST_PORT} vendor2=${VENDOR2_HOST_PORT}"

# Build all images required by the multi-actor stack.
log "Building images..."
docker compose -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" build

# Start the full stack.  demo-runner declares condition: service_healthy for
# every actor service (DEMO-MA-02-002), so it only launches once all actors
# pass their /health/ready probe.  --abort-on-container-exit halts the stack
# when demo-runner exits; --exit-code-from propagates its exit code so a
# failed scenario is distinguishable from a failed service start.
log "Starting multi-actor stack and running scenario '${DEMO}'..."
DEMO="${DEMO}" docker compose \
    -f "${COMPOSE_FILE}" \
    -p "${PROJECT_NAME}" \
    up \
    --abort-on-container-exit \
    --exit-code-from demo-runner \
    && DEMO_EXIT=0 || DEMO_EXIT=$?

if [ "${DEMO_EXIT}" -ne 0 ]; then
    fail "Scenario '${DEMO}' exited with status ${DEMO_EXIT}."
fi

log "SUCCESS: scenario '${DEMO}' passed."
