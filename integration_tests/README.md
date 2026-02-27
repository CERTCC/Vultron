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

## Notes

- The integration test script stops the `api-dev` and `demo` containers on
  exit (success or failure) to leave a clean environment.
- These tests require a working Docker daemon and sufficient resources to run
  the full demo suite.
- Individual unit tests for the demo CLI live in `test/demo/` and are run
  as part of the normal `pytest` suite.
