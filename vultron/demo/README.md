# Vultron Demo Suite

This directory contains the Vultron ActivityPub workflow demo scripts and the
unified demo CLI.

## Overview

The demo suite walks through the Vultron Coordinated Vulnerability Disclosure
(CVD) protocol. Demos are organized into two sub-packages reflecting two
distinct techniques:

- **`exchange/`** — Individual protocol-fragment demos. Each script
  demonstrates a single ActivityStreams message exchange using direct inbox
  injection. These are for exploring protocol message semantics with a single
  running API server. See `exchange/README.md` for the full list.

- **`scenario/`** — End-to-end multi-actor workflow demos. Each script
  orchestrates a complete CVD workflow across separate API server containers
  using trigger-based puppeteering, so that each actor's own behavior tree
  and outbox logic is exercised. See `scenario/README.md` for the full list.

### Exchange demos (`exchange/`)

| Sub-command              | What it demonstrates                                  |
|--------------------------|-------------------------------------------------------|
| `receive-report`         | Receiving and processing a vulnerability report       |
| `initialize-case`        | Creating and initializing a vulnerability case        |
| `initialize-participant` | Initializing a standalone CaseParticipant             |
| `invite-actor`           | Inviting an actor to participate in a case            |
| `establish-embargo`      | Establishing a coordinated disclosure embargo         |
| `acknowledge`            | Acknowledging receipt of a vulnerability report       |
| `status-updates`         | Posting case status updates and notes                 |
| `suggest-actor`          | Suggesting an actor for a case                        |
| `transfer-ownership`     | Transferring case ownership between actors            |
| `manage-case`            | Managing report management state transitions          |
| `manage-embargo`         | Managing embargo lifecycle state transitions          |
| `manage-participants`    | Adding and removing case participants                 |

### Scenario demos (`scenario/`)

| Sub-command    | What it demonstrates                                      |
|----------------|-----------------------------------------------------------|
| `two-actor`    | Two-actor (Finder + Vendor) multi-container CVD workflow  |
| `three-actor`  | Three-actor (+ Coordinator) multi-container CVD workflow  |
| `multi-vendor` | Ownership transfer + second vendor multi-container demo   |

The `vultrabot` sub-group provides standalone behavior-tree demos (pacman,
robot, cvd) that do not require a running API server.

## Prerequisites

- Docker and Docker Compose (for docker-compose usage)
- Python 3.12+ and `uv` (for direct usage)
- A running Vultron API server (for all demos except `vultrabot`)

## Running demos via Docker Compose

Docker Compose is the recommended way to run the demos. The `demo` container
depends on `api-dev` (with a health-check condition), so starting `demo` will
also start the API server if it is not already running.

### Interactive mode (default)

```bash
# From the repository root
docker compose -f docker/docker-compose.yml run --rm demo
```

This drops you into a shell where you can invoke `vultron-demo` directly:

```bash
vultron-demo --help
vultron-demo receive-report
vultron-demo all
```

### Non-interactive mode

Set the `DEMO` environment variable to the sub-command name to run a single
demo non-interactively and exit:

```bash
DEMO=receive-report docker compose -f docker/docker-compose.yml up demo
```

To run all demos in sequence:

```bash
DEMO=all docker compose -f docker/docker-compose.yml up demo
```

## Running demos directly (without Docker)

First install the package and start the API server:

```bash
uv pip install -e .
uv run uvicorn vultron.api.main:app --host localhost --port 7999 --reload
```

Then in a separate terminal, run the unified CLI:

```bash
vultron-demo --help
vultron-demo receive-report
vultron-demo all
```

Enable debug logging with `--debug`, or write logs to a file with
`--log-file PATH`:

```bash
vultron-demo --debug receive-report
vultron-demo --log-file /tmp/demo.log all
```

### Running individual scripts directly

Each demo script remains directly invokable as a Python module:

```bash
uv run python -m vultron.demo.exchange.receive_report_demo
uv run python -m vultron.demo.scenario.two_actor_demo
```

## Unified CLI (`vultron-demo`)

`vultron/demo/cli.py` implements the unified CLI using
[click](https://click.palletsprojects.com/). The entry point is registered in
`pyproject.toml`:

```text
vultron-demo = "vultron.demo.cli:main"
```

Key sub-commands:

- **`<demo-name>`** — run a single named demo (e.g., `receive-report`)
- **`all`** — run every demo in sequence; stops on first failure and prints a
  pass/fail summary
- **`vultrabot`** — standalone BT sub-group (no API required)

## Shared utilities (`vultron/demo/utils.py`)

All demo scripts import shared helpers from `vultron.demo.utils`:

- `demo_step` / `demo_check` — context managers for structured step logging
- `DataLayerClient` — thin HTTP client for the Vultron DataLayer admin API
- `demo_environment` — context manager that sets up a clean DataLayer
  context on entry and tears it down (even on exception) on exit
- `post_to_inbox_and_wait` — post an ActivityStreams activity and wait for
  processing
- `setup_clean_environment`, `reset_datalayer`, `discover_actors`,
  `check_server_availability`, and other shared helpers

## Demo isolation

Each demo uses `demo_environment(client)` as a context manager around its
main logic. On entry the DataLayer is reset to a known-clean state; on exit
(including on exception) all created objects are deleted. This means demos
can be run individually or in sequence via `all` without interfering with
each other.

## Integration testing

A full end-to-end integration test that runs all demos inside Docker is
available:

```bash
make integration-test
```

See `integration_tests/README.md` for details.
