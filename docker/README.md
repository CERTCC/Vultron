# Docker Setup for Vultron

## Available Services

This docker-compose setup provides several containerized services:

- **api-dev**: Development API server running on port 7999
- **receive-report-demo**: Demo script that sends vulnerability reports to the API server
- **initialize-case-demo**: Demo script that shows the case initialization workflow
- **establish-embargo-demo**: Demo script that demonstrates the embargo establishment workflow
- **invite-actor-demo**: Demo script that demonstrates inviting an actor to a case
- **status-updates-demo**: Demo script that demonstrates case and participant status updates
- **suggest-actor-demo**: Demo script that demonstrates recommending actors for a case
- **transfer-ownership-demo**: Demo script that demonstrates transferring case ownership
- **test**: Run pytest test suite
- **docs**: Documentation server on port 8000
- **vultrabot-demo**: Vultrabot demonstration

## Running the API Server and Demo

To run both the API server and a demo together, for example:

```bash
docker-compose up api-dev receive-report-demo
```

Replace `receive-report-demo` with any of the demo service names listed above.
Each demo container will:

1. Wait for the API server to start
2. Connect to the API via the internal Docker network
3. Execute the demonstration workflow
4. Display results and exit

The API server remains running and accessible on `http://localhost:7999`.

To run just the API server:

```bash
docker-compose up api-dev
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
