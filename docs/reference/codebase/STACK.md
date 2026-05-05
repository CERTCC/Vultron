# Technology Stack

## Core Sections (Required)

### 1) Runtime Summary

| Area | Value | Evidence |
|------|-------|----------|
| Primary language | Python | `pyproject.toml`, `docs/reference/codebase/.codebase-scan.txt` |
| Runtime + version | Python `>=3.12`; Docker and CI use Python 3.13 | `pyproject.toml`, `docker/Dockerfile`, `.github/workflows/python-app.yml` |
| Package manager | `uv` for dependency sync and command execution | `Makefile`, `.github/workflows/python-app.yml`, `docker/Dockerfile` |
| Module/build system | Setuptools build backend with `uv build` packaging | `pyproject.toml`, `.github/workflows/python-app.yml` |

### 2) Production Frameworks and Dependencies

| Dependency | Version | Role in system | Evidence |
|------------|---------|----------------|----------|
| `fastapi` | `>=0.136.0` | HTTP API and router layer | `pyproject.toml`, `vultron/adapters/driving/fastapi/app.py` |
| `uvicorn` | `>=0.46.0` | ASGI server for the API | `pyproject.toml`, `docker/Dockerfile` |
| `pydantic` | `==2.13.3` | Model validation and typed request/object models | `pyproject.toml`, `vultron/core/ports/datalayer.py` |
| `sqlmodel` | `>=0.0.38` | SQLite-backed persistence adapter | `pyproject.toml`, `vultron/adapters/driven/datalayer_sqlite.py` |
| `py-trees` | `>=2.2.0` | Behavior-tree implementation support | `pyproject.toml`, `docs/adr/0002-model-processes-with-behavior-trees.md` |
| `transitions` | `>=0.9.3` | State-machine support | `pyproject.toml` |
| `pyyaml` | `>=6.0` | YAML-backed config and metadata loading | `pyproject.toml`, `vultron/demo/cli.py` |
| `mkdocs` + Material plugins | mixed | Built documentation site and reference docs | `pyproject.toml`, `mkdocs.yml` |

### 3) Development Toolchain

| Tool | Purpose | Evidence |
|------|---------|----------|
| `black` | Python formatting | `pyproject.toml`, `.pre-commit-config.yaml` |
| `flake8` | Python linting | `pyproject.toml`, `.flake8`, `.github/workflows/python-app.yml` |
| `mypy` | Static type checking | `pyproject.toml`, `.github/workflows/python-app.yml` |
| `pyright` | Static type checking | `pyproject.toml`, `pyrightconfig.json`, `.github/workflows/python-app.yml` |
| `pytest` | Automated tests | `pyproject.toml`, `test/AGENTS.md` |
| `markdownlint-cli2` | Markdown linting/fixing | `.pre-commit-config.yaml`, `.markdownlint-cli2.yaml` |
| `pre-commit` | Hook orchestration | `pyproject.toml`, `.pre-commit-config.yaml` |
| `npm` packages `markdownlint` and `madr` | Markdown/ADR authoring support | `package.json` |

### 4) Key Commands

```bash
uv sync --dev
uv build
uv run pytest --tb=short 2>&1 | tail -5
uv run flake8 vultron/ test/
```

### 5) Environment and Config

- Config sources: `.env.example`, `pyproject.toml`, `docker/docker-compose.yml`,
  `docker/docker-compose-multi-actor.yml`
- Required env vars seen in committed files: `PROJECT_NAME`, `LOG_LEVEL`,
  `VULTRON_DB_URL`, `VULTRON_BASE_URL`, `VULTRON_API_BASE_URL`,
  `VULTRON_ACTOR_ID`, `VULTRON_SEED_CONFIG`, `VULTRON_ACTOR_NAME`,
  `VULTRON_ACTOR_TYPE`
- Deployment/runtime constraints: default persistence is SQLite; Docker Compose
  runs the API with `uvicorn vultron.adapters.driving.fastapi.main:app`; the
  multi-actor setup expects one SQLite volume per actor service.

### 6) Evidence

- `pyproject.toml`
- `docker/Dockerfile`
- `.github/workflows/python-app.yml`
- `Makefile`
- `package.json`
- `docs/reference/codebase/.codebase-scan.txt`
