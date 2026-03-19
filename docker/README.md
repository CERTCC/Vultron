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

## Networking

The containers communicate via a dedicated Docker bridge network (`vultron-network`). The demo container accesses the API server using the service name `api-dev` as the hostname, which Docker resolves internally.

## Customizing the docker setup

We use a project name to namespace the docker containers, networks, and volumes created by docker-compose. By default, this is derived from the name of the directory containing the `docker-compose.yml` file.
To avoid naming conflicts, you can customize the project name in one of the following ways:

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

Both variables are set for compatibility with different docker-compose versions.

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
