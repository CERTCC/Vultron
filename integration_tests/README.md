# Integration Tests

This directory contains manual acceptance tests for the Vultron project.
These tests are **not run by `pytest`** and are intended for acceptance
testing before releases or after significant changes to the demo suite.

## Prerequisites

- Docker and Docker Compose available on `PATH`
- Built Docker images (the scripts will build them if necessary)
- Run all commands from the **repository root**

## Demo Integration Test (DC-06-001)

`integration_tests/demo/run_demo_integration_test.sh` starts the `api-dev`
service, waits for it to become healthy, then runs the unified
`vultron-demo all` command inside the `demo` container and reports whether
all demos passed.

### Running the test

```bash
make integration-test
```

Or directly:

```bash
./integration_tests/demo/run_demo_integration_test.sh
```

### What success looks like

The script prints `[integration-test] SUCCESS: all demos passed.` and exits
with status `0`.

### What failure looks like

The script prints `[integration-test] FAIL: ...` and exits with a non-zero
status. Check the Docker logs for the `api-dev` and `demo` containers for
details:

```bash
docker compose -f docker/docker-compose.yml logs api-dev
docker compose -f docker/docker-compose.yml logs demo
```

## Multi-Actor Demo Integration Tests (DEMO-MA-03-001)

`integration_tests/demo/run_multi_actor_integration_test.sh` starts all
actor services defined in `docker/docker-compose-multi-actor.yml`, waits for
every actor to pass its `/health/ready` health check, then runs the selected
multi-actor demo scenario via the `demo-runner` service.

Three scenarios are supported:

| Scenario      | Actors                                      |
|:--------------|:--------------------------------------------|
| `two-actor`   | Finder + Vendor + CaseActor                 |
| `three-actor` | Finder + Vendor + Coordinator + CaseActor   |
| `multi-vendor`| Finder + Vendor + Coordinator + Vendor2 + CaseActor |

### Running a specific scenario

```bash
# Two-actor scenario (default):
make integration-test-multi-actor

# Three-actor scenario:
make integration-test-three-actor

# Multi-vendor scenario:
make integration-test-multi-vendor
```

Or directly, passing the scenario as a positional argument:

```bash
./integration_tests/demo/run_multi_actor_integration_test.sh two-actor
./integration_tests/demo/run_multi_actor_integration_test.sh three-actor
./integration_tests/demo/run_multi_actor_integration_test.sh multi-vendor
```

### What success looks like

The script prints
`[multi-actor-integration] SUCCESS: scenario '<name>' passed.` and exits
with status `0`.

### What failure looks like

The script prints `[multi-actor-integration] FAIL: ...` and exits with a
non-zero status. Check the Docker logs for details:

```bash
docker compose -f docker/docker-compose-multi-actor.yml logs
```

### Isolation

The script uses `PROJECT_NAME=vultron-it` by default to avoid conflicting
with a running development stack. Override it to run multiple scenarios in
parallel:

```bash
PROJECT_NAME=vultron-it-two   DEMO=two-actor   ./integration_tests/demo/run_multi_actor_integration_test.sh
PROJECT_NAME=vultron-it-three DEMO=three-actor ./integration_tests/demo/run_multi_actor_integration_test.sh
```

**Host port conflicts** — by default each actor service binds container
port 7999 to an ephemeral host port chosen by Docker (equivalent to
`${VAR:-0}` in the compose file), so port conflicts are unlikely in normal
use. If you need to pin specific host ports (e.g. for manual debugging or
to run concurrent scenarios), use the `*_HOST_PORT` env vars:

```bash
FINDER_HOST_PORT=17901 VENDOR_HOST_PORT=17902 \
CASE_ACTOR_HOST_PORT=17903 COORDINATOR_HOST_PORT=17904 \
VENDOR2_HOST_PORT=17905 \
./integration_tests/demo/run_multi_actor_integration_test.sh
```

Use `docker compose port <service> 7999` or `docker ps` to discover the
dynamically assigned host port when running with ephemeral defaults.

Named Docker volumes are removed on exit so each run starts from a clean
baseline (DEMO-MA-01-003).

## Notes

- The integration test script stops the `api-dev` and `demo` containers on
  exit (success or failure) to leave a clean environment.
- These tests require a working Docker daemon and sufficient resources to run
  the full demo suite.
- Individual unit tests for the demo CLI live in `test/demo/` and are run
  as part of the normal `pytest` suite.
