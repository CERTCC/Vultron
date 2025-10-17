PROJECT_HOME := .
VULTRON_DIR := $(PROJECT_HOME)/vultron
TEST_DIR := $(PROJECT_HOME)/test

# Display help information about available targets
.PHONY: help
help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

# set up dev environment
.PHONY: setup_dev
setup_dev:  ## Set up development environment
	uv sync --dev

# upgrade dev dependencies
.PHONY: upgrade_dev
upgrade_dev:  ## Upgrade dev dependencies
	uv sync --upgrade --dev

# upgrade dependencies
.PHONY: upgrade_deps
upgrade_deps:  ## Upgrade all dependencies
	uv sync --upgrade

# run tests locally
.PHONY: test
test:  ## Run tests locally
	uv run pytest test

# black code formatting
.PHONY: black
black:  ## Format code with black
	uv run black .

# markdownlint-cli2 code formatting
.PHONY: mdlint
mdlint:  ## Lint markdown files
	./mdlint.sh

# flake8
.PHONY: flake8
flake8:  ## Check code with flake8
	# edit $(PROJECT_HOME)/.flake8 to configure flake8 options
	uv run flake8 ${VULTRON_DIR} ${TEST_DIR}

# flake8 code linting
.PHONY: flake8-lint
flake8-lint:  ## Lint code with flake8
	# edit $(PROJECT_HOME)/.flake8 to configure flake8 options
	uv run flake8 --exit-zero ${VULTRON_DIR} ${TEST_DIR}

# mypy type checking
.PHONY: mypy
mypy:  ## Run mypy for type checking
	# edit $(PROJECT_HOME)/.mypy.ini to configure mypy options
	uv run mypy

# run all linters
.PHONY: lint
lint: black mdlint flake8-lint mypy ## Run all linters (black, markdownlint)

# serve docs locally
.PHONY: docs
docs:  ## Serve documentation locally
	uv run mkdocs serve

# build docker images
.PHONY: docker_build
docker_build:  ## Build docker images
	cd docker && docker-compose build

# docker compose up
.PHONY: docker_up
docker_up:  ## Start docker containers
	cd docker && docker-compose up -d

# rebuild docker images and up
.PHONY: docker_rebuild
docker_rebuild:  ## Rebuild and restart docker containers
	cd docker && docker-compose up -d --build --force-recreate


.PHONY: api_dev
api_dev:  ## Start API server in development mode
	uv run uvicorn vultron.api:app --reload --port 7999

.PHONY: docker_api_dev
docker_api_dev: docker_up  ## Start API server in Docker in development mode
	cd docker && docker-compose up api-dev