# Docker Setup for Vultron

## Customizing the docker setup

We use a project name to namespace the docker containers, networks, and volumes created by docker-compose. By default, this is derived from the name of the directory containing the `docker-compose.yml` file.
To avoid naming conflicts, you can customize the project name in one of the following ways:

### Create a `.env` file

```dotenv
# Environment Variables for Docker Setup
# Copy this file to .env and modify the values as needed
# before using it with Docker Compose.
PROJECT_NAME=vultron
```

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
