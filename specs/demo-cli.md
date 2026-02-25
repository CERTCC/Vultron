# Demo CLI Specification

## Overview

Requirements for a unified demo command-line interface that aggregates all
individual Vultron demo scripts into a single invokable entry point. Covers
CLI structure, demo isolation, Docker packaging, and test requirements.

**Source**: `plan/IDEATION.md` (Unify demos), `plan/PRIORITIES.md`
(PRIORITY 10)
**Cross-references**: `tech-stack.md`, `testability.md`,
`prototype-shortcuts.md`

---

## CLI Interface (MUST)

- `DC-01-001` The unified demo MUST be implemented as a `click`-based CLI
  script at `vultron/demo/cli.py`
  - Entry point MUST be registered in `pyproject.toml` as
    `vultron-demo = "vultron.demo.cli:main"`
- `DC-01-002` The CLI MUST provide a sub-command for each individual demo
  - Each sub-command name MUST match the short name of the corresponding demo
    script (e.g., `receive-report`, `initialize-case`)
- `DC-01-003` The CLI MUST provide an `all` sub-command that runs every demo
  in sequence
  - The `all` sub-command MUST stop and report failure if any individual demo
    fails
- `DC-01-004` The CLI MUST print a human-readable summary on completion of
  the `all` sub-command indicating which demos passed and which failed
- `DC-01-005` Individual demo scripts MUST retain their existing
  `if __name__ == "__main__"` entry points so they remain directly invokable

## Demo Utilities (MUST)

- `DC-02-001` Shared demo utilities (`demo_step`, `demo_check` context
  managers and HTTP client helpers) MUST be extracted to `vultron/demo/utils.py`
  - All demo scripts MUST import from `vultron.demo.utils`
  - No demo script MAY define its own copy of `demo_step`, `demo_check`, or
    equivalent helper utilities
- `DC-02-002` Demo scripts MUST be relocated to `vultron/demo/` and MUST be
  importable as `vultron.demo.<script_name>`

## Demo Isolation (MUST)

- `DC-03-001` Each demo MUST include setup and teardown logic that leaves the
  DataLayer in a clean state after the demo completes
  - Teardown MUST run even if the demo raises an exception
- `DC-03-002` Demos run in sequence (via the `all` sub-command) MUST NOT
  share mutable state; each demo MUST operate on a freshly initialized
  DataLayer context
- `DC-03-003` The CLI MUST NOT assume a globally pre-initialized DataLayer;
  each demo invocation MUST create and clean up its own context

## Docker Packaging (MUST)

- `DC-04-001` The unified demo MUST be packaged as a Docker service
  (`demo` service in `docker/docker-compose.yml`)
  - The `demo` container MUST depend on `api-dev` with
    `condition: service_healthy`
- `DC-04-002` The Docker entry point MUST launch the unified CLI so that the
  container runs interactively and prompts the user to select a demo
  - When the `DEMO` environment variable is set, the container MUST run the
    named sub-command non-interactively and exit
- `DC-04-003` Individual per-demo Docker services (one service per demo
  script) MUST be removed from `docker-compose.yml` once the unified demo
  service is operational

## Unit Testing (MUST)

- `DC-05-001` The unified CLI MUST have unit tests in
  `test/demo/test_cli.py`
- `DC-05-002` Unit tests for the `all` sub-command MUST mock or stub the
  individual demo functions and verify that every registered demo is invoked
  exactly once in the expected order
- `DC-05-003` Unit tests MUST verify that the CLI exits with a non-zero
  status code when any demo sub-command raises an exception
- `DC-05-004` Unit tests for each sub-command MUST verify the sub-command
  invokes the correct underlying demo function

## Integration Testing (SHOULD)

- `DC-06-001` An integration test script SHOULD exist at
  `integration_tests/demo/run_demo_integration_test.sh` (or equivalent
  Python script) that:
  1. Starts the `api-dev` service and waits for it to be healthy
  2. Runs the unified demo `all` sub-command inside the `demo` container
  3. Verifies all demos complete without errors
- `DC-06-002` A `integration_tests/README.md` MUST document how to run the
  integration tests and what success looks like
  - The README MUST state that these tests are manual (not run by `pytest`)
    and are intended for acceptance testing before releases
- `DC-06-003` The integration test SHOULD be runnable via a `Makefile`
  target (e.g., `make integration-test`)

## Verification

### DC-01-001 through DC-01-005 Verification

- Unit test: `vultron-demo --help` lists all individual demo sub-commands
- Unit test: `vultron-demo all` invokes all demos in order
- Integration test: CLI installed as package entry point per `pyproject.toml`

### DC-02-001, DC-02-002 Verification

- Code review: No demo script defines `demo_step`/`demo_check` locally
- Unit test: `from vultron.demo.utils import demo_step, demo_check` succeeds

### DC-03-001 through DC-03-003 Verification

- Unit test: Demo teardown mock is called even when demo body raises
- Integration test: Running `all` twice in sequence produces consistent results

### DC-04-001 through DC-04-003 Verification

- Manual test: `docker compose up demo` runs demos interactively
- Code review: Old per-demo services removed after unified service verified

### DC-05-001 through DC-05-004 Verification

- CI: `uv run pytest test/demo/test_cli.py` passes with all demo stubs

### DC-06-001 through DC-06-003 Verification

- Manual test: `integration_tests/README.md` instructions produce passing run

## Related

- **Tech Stack**: `specs/tech-stack.md`
- **Testability**: `specs/testability.md`
- **Prototype Shortcuts**: `specs/prototype-shortcuts.md`
- **Priorities**: `plan/PRIORITIES.md` (PRIORITY 10 DEMO-4)
- **Codebase Structure**: `notes/codebase-structure.md` (TECHDEBT-2)
- **Implementation Plan**: `plan/IMPLEMENTATION_PLAN.md` (TECHDEBT-2)
- **Demo utilities pattern**: `AGENTS.md` (Demo Script Lifecycle Logging)
