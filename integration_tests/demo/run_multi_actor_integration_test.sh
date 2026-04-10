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
#   FINDER_HOST_PORT      Pin a specific host port for the finder service.
#   VENDOR_HOST_PORT      Pin a specific host port for the vendor service.
#   CASE_ACTOR_HOST_PORT  Pin a specific host port for the case-actor service.
#   COORDINATOR_HOST_PORT Pin a specific host port for the coordinator service.
#   VENDOR2_HOST_PORT     Pin a specific host port for the vendor2 service.
#   COMPOSE_SERVICE_COLORS
#                         Path to a service-colors.env file that maps service
#                         names to hex colors (default: docker/service-colors.env).
#                         Colors are applied only when stdout is a TTY; output
#                         redirected to a file or pipe passes through unmodified.
#                         See docker/service-colors.env for format and defaults.
#
#   Host port variables are optional.  When unset (the default), Docker
#   assigns an ephemeral host port for each service automatically, so no
#   port conflicts with a running development stack can occur.  All
#   inter-actor communication happens over the internal vultron-network
#   bridge and is unaffected by host port assignment.
#
#   To inspect the assigned host ports after startup:
#     docker compose -f docker/docker-compose-multi-actor.yml port finder 7999
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
COLORIZER="${SCRIPT_DIR}/colorize_compose_logs.py"
PROJECT_NAME="${PROJECT_NAME:-vultron-it}"
DEMO="${1:-${DEMO:-two-actor}}"

VALID_SCENARIOS="two-actor three-actor multi-vendor"
if ! echo "${VALID_SCENARIOS}" | grep -qw "${DEMO}"; then
    echo "ERROR: unknown scenario '${DEMO}'. Valid options: ${VALID_SCENARIOS}" >&2
    exit 1
fi

log()  { echo "[multi-actor-integration] $*"; }
fail() { log "FAIL: $*"; exit 1; }

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

# Build all images required by the multi-actor stack.
log "Building images..."
docker compose -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" build

# Start the full stack.  demo-runner declares condition: service_healthy for
# every actor service (DEMO-MA-02-002), so it only launches once all actors
# pass their /health/ready probe.  --abort-on-container-exit halts the stack
# when demo-runner exits; --exit-code-from propagates its exit code so a
# failed scenario is distinguishable from a failed service start.
#
# --ansi=never strips docker compose's own (non-deterministic) color codes so
# the colorize_compose_logs.py filter can apply the configured per-service
# colors consistently.  The filter is a no-op when stdout is not a TTY, so
# captured/redirected output remains plain text.
log "Starting multi-actor stack and running scenario '${DEMO}'..."
DEMO="${DEMO}" docker compose \
    -f "${COMPOSE_FILE}" \
    -p "${PROJECT_NAME}" \
    --ansi=never \
    up \
    --abort-on-container-exit \
    --exit-code-from demo-runner \
    2>&1 | python3 "${COLORIZER}" \
    && DEMO_EXIT=0 || DEMO_EXIT=$?

if [ "${DEMO_EXIT}" -ne 0 ]; then
    fail "Scenario '${DEMO}' exited with status ${DEMO_EXIT}."
fi

log "SUCCESS: scenario '${DEMO}' passed."
