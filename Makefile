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

# run all linters
.PHONY: lint
lint: black mdlint  ## Run all linters (black, markdownlint)

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
