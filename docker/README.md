# Docker Setup for Vultron

## Available Services

This docker-compose setup provides the following containerized services:

- **api-dev**: Development API server running on port 7999
- **demo**: Unified demo runner for all Vultron demo scripts
- **test**: Run the pytest test suite
- **docs**: MkDocs documentation server on port 8000
- **vultrabot-demo**: Standalone Vultrabot behaviour-tree demonstration

## Running the API Server

To start just the API server:

```bash
docker-compose up api-dev
```

The API server will be accessible at `http://localhost:7999`.

## Running Demos

All demos are provided through the unified `demo` service, which uses the
`vultron-demo` CLI entry point. The `demo` service waits for the API server
to be healthy before running.

### Run a specific demo non-interactively

Set the `DEMO` environment variable to the name of the demo sub-command:

```bash
DEMO=receive-report docker-compose up api-dev demo
```

Available demo sub-commands:

- `acknowledge`
- `all` (run every demo in sequence)
- `establish-embargo`
- `initialize-case`
- `initialize-participant`
- `invite-actor`
- `manage-case`
- `manage-embargo`
- `manage-participants`
- `receive-report`
- `status-updates`
- `suggest-actor`
- `transfer-ownership`
- `trigger`
- `vultrabot`

### Run demos interactively

Without the `DEMO` variable, the container drops into an interactive shell
where you can run any demo manually:

```bash
docker-compose run --rm demo
# Inside the container:
vultron-demo receive-report
vultron-demo all
```

The API server must be running before starting the demo container in
interactive mode:

```bash
docker-compose up -d api-dev
docker-compose run --rm demo
```

## Multi-Actor Demo Setup

`docker-compose-multi-actor.yml` defines four isolated actor services
(`finder`, `vendor`, `coordinator`, `case-actor`) plus a `demo-runner` for
multi-actor demo scenarios (D5-2 and later).

### Services and port mappings

| Service      | Host port | Docker-internal URL                      |
|:-------------|----------:|:-----------------------------------------|
| `finder`     |      7901 | `http://finder:7999/api/v2/`             |
| `vendor`     |      7902 | `http://vendor:7999/api/v2/`             |
| `coordinator`|      7904 | `http://coordinator:7999/api/v2/`        |
| `case-actor` |      7903 | `http://case-actor:7999/api/v2/`         |
| `demo-runner`|         — | (no host port; uses vultron-network)     |

### Required environment variables

| Variable              | Default value             | Purpose                               |
|:----------------------|:--------------------------|:--------------------------------------|
| `PROJECT_NAME`        | `vultron`                 | Docker resource name prefix           |
| `COMPOSE_PROJECT_NAME`| `vultron`                 | Docker Compose project name           |
| `VULTRON_BASE_URL`    | *(set per service)*       | Container's own API base URL          |
| `VULTRON_DB_PATH`     | `/app/data/mydb.json`     | Path to TinyDB file inside container  |
| `VULTRON_ACTOR_ID`    | *(set per service)*       | Deterministic full actor URI          |
| `VULTRON_SEED_CONFIG` | *(set per service)*       | Seed config JSON for local + peers    |

### Run the D5-2 two-actor acceptance scenario

The `demo-runner` service now performs the D5-2 scenario end to end:
it waits for healthy actor services, resets container state to a clean
baseline, seeds Finder/Vendor, runs the workflow, verifies final state,
and exits non-interactively.

```bash
# From the docker/ directory:
docker compose -f docker-compose-multi-actor.yml up --abort-on-container-exit demo-runner
```

This is the canonical single-command acceptance run for the current
two-actor scenario.

### Run the D5-3 three-actor acceptance scenario

The same compose file can also run the coordinator-based D5-3 flow:

```bash
# From the docker/ directory:
DEMO=three-actor docker compose -f docker-compose-multi-actor.yml \
    up --abort-on-container-exit demo-runner
```

This starts Finder, Vendor, Coordinator, and CaseActor, resets their
DataLayers, seeds all peers, and runs the deterministic three-actor scenario
end to end.

### Run the D5-4 multi-vendor acceptance scenario

The multi-vendor (ownership-transfer) scenario uses all five actor services:

```bash
# From the docker/ directory:
DEMO=multi-vendor docker compose -f docker-compose-multi-actor.yml \
    up --abort-on-container-exit demo-runner
```

### Automated multi-actor integration tests (D5-5)

Each scenario can also be run via the integration test script, which builds
the images, runs the full stack, verifies the exit code, and removes all
volumes on exit for a clean baseline:

```bash
# From the repository root:
./integration_tests/demo/run_multi_actor_integration_test.sh two-actor
./integration_tests/demo/run_multi_actor_integration_test.sh three-actor
./integration_tests/demo/run_multi_actor_integration_test.sh multi-vendor
```

Or via the Makefile targets:

```bash
make integration-test-multi-actor    # two-actor
make integration-test-three-actor    # three-actor
make integration-test-multi-vendor   # multi-vendor
```

See `integration_tests/README.md` for full usage notes and isolation tips.

### Start the multi-actor services manually

```bash
# From the docker/ directory:
docker compose -f docker-compose-multi-actor.yml up -d \
    finder vendor coordinator case-actor
```

All three services expose `/api/v2/health/ready` and will be marked healthy
once their DataLayer is reachable.

### Seed actor records

Each API server starts without any actor records in its DataLayer.  Run the
`vultron-demo seed` command against each container to create the local actor
and register peer actors:

```bash
# Seed each actor service from the demo-runner container:
docker compose -f docker-compose-multi-actor.yml run --rm \
    -e VULTRON_API_BASE_URL=http://finder:7999/api/v2 demo-runner \
    vultron-demo seed

docker compose -f docker-compose-multi-actor.yml run --rm \
    -e VULTRON_API_BASE_URL=http://vendor:7999/api/v2 demo-runner \
    vultron-demo seed

docker compose -f docker-compose-multi-actor.yml run --rm \
    -e VULTRON_API_BASE_URL=http://coordinator:7999/api/v2 demo-runner \
    vultron-demo seed

docker compose -f docker-compose-multi-actor.yml run --rm \
    -e VULTRON_API_BASE_URL=http://case-actor:7999/api/v2 demo-runner \
    vultron-demo seed
```

The D5-2 and D5-3 demos reset state and handle peer registration
automatically. Manual seeding remains useful for debugging or for future
scenarios that do not use the `demo-runner` workflow.

### Reset actor state between runs

Named volumes (`finder-data`, `vendor-data`, `case-actor-data`) persist the
TinyDB files across container restarts.  To wipe all state and start fresh:

```bash
docker compose -f docker-compose-multi-actor.yml down -v
```

## Networking

The containers communicate via a dedicated Docker bridge network
(`vultron-network`). The demo container accesses the API server using the
service name `api-dev` as the hostname, which Docker resolves internally.

For multi-actor setups, each container uses its service name as the hostname
in `VULTRON_BASE_URL` (e.g., `http://finder:7999/api/v2/`) so that peer
containers can derive inbox URLs that route correctly on the Docker network.

## Customizing the docker setup

We use a project name to namespace the docker containers, networks, and
volumes created by docker-compose. By default, this is derived from the
name of the directory containing the `docker-compose.yml` file.
To avoid naming conflicts, you can customize the project name in one of the
following ways:

### Create a `.env` file

Copy the `.env.example` file to `.env`:

```bash
cp .env.example .env
```

The file contains:

```dotenv
# Environment Variables for Docker Setup
PROJECT_NAME=vultron
COMPOSE_PROJECT_NAME=vultron
```

Both variables are set for compatibility with different docker-compose
versions.

### Set a different project name at runtime

To avoid or override a `.env`, you can invoke docker-compose with

```bash
PROJECT_NAME=vultron docker-compose up
```

or export the variable in your shell session

```bash
export PROJECT_NAME=vultron
docker-compose up
```
