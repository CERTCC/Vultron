# Technology Stack

## Core Sections (Required)

### 1) Runtime Summary

| Area | Value | Evidence |
|------|-------|----------|
| Primary language | Python | `pyproject.toml`, `docs/reference/codebase/.codebase-scan.txt` |
| Runtime + version | Python `>=3.12`; CI and Docker use Python `3.13` | `pyproject.toml`, `.github/actions/setup-python-uv/action.yml`, `docker/Dockerfile` |
| Package manager | `uv` for sync, execution, and builds | `Makefile`, `.github/actions/setup-python-uv/action.yml`, `docker/Dockerfile` |
| Module/build system | `setuptools.build_meta` with `setuptools-scm` dynamic versioning | `pyproject.toml` |

### 2) Production Frameworks and Dependencies

| Dependency | Version | Role in system | Evidence |
|------------|---------|----------------|----------|
| `fastapi` | `>=0.137.1` | HTTP API and driving adapter layer | `pyproject.toml`, `vultron/adapters/driving/fastapi/app.py` |
| `uvicorn` | `>=0.49.0` | ASGI server for the API | `pyproject.toml`, `docker/Dockerfile` |
| `pydantic` | `==2.13.4` | Validation for config, domain, and wire models | `pyproject.toml`, `vultron/config.py` |
| `pydantic-settings` | `>=2.14.2` | Environment-driven config loading | `pyproject.toml`, `vultron/config.py` |
| `sqlmodel` | `>=0.0.38` | SQLite-backed persistence adapter | `pyproject.toml`, `vultron/adapters/driven/datalayer_sqlite/datalayer.py` |
| `py-trees` | `>=2.2.0` | Behavior-tree execution model | `pyproject.toml`, `AGENTS.md` |
| `transitions` | `>=0.9.3` | State-machine support | `pyproject.toml` |
| `httpx2` | unpinned | HTTP client package used by delivery and demo helpers | `pyproject.toml`, `vultron/adapters/driven/demo_http_delivery.py`, `vultron/adapters/driven/asgi_emitter.py` |
| `click` | `>=8.4.1` | CLI framework for demo and metadata commands | `pyproject.toml`, `vultron/demo/cli.py` |
| `pyyaml` | `>=6.0` | YAML config and metadata parsing | `pyproject.toml`, `vultron/config.py` |
| `python-frontmatter` | `>=1.3.0` | Notes/history metadata parsing | `pyproject.toml` |
| `mkdocs` plus Material/doc plugins | mixed | Documentation site generation | `pyproject.toml`, `mkdocs.yml` |
| `networkx` | `>=3.5` | Case-state graph computations | `pyproject.toml`, `vultron/core/case_states/hypercube.py` |
| `owlready2` + `rdflib` | `>=0.48`, `>=7.2.1` | Ontology tooling | `pyproject.toml`, `vultron/scripts/ontology2md.py` |
| `pandas` + `scipy` | `>=3.0.3`, `>=1.16.2` | Analysis/demo support | `pyproject.toml`, `vultron/demo/vultrabot.py` |

### 3) Development Toolchain

| Tool | Purpose | Evidence |
|------|---------|----------|
| `black` | Python formatting | `pyproject.toml`, `.pre-commit-config.yaml` |
| `flake8` | Python linting | `pyproject.toml`, `.flake8`, `.github/workflows/python-app.yml` |
| `mypy` | Static type checking | `pyproject.toml`, `.mypy.ini`, `.github/workflows/python-app.yml` |
| `pyright` | Static type checking | `pyproject.toml`, `pyrightconfig.json`, `.github/workflows/python-app.yml` |
| `pytest` + `pytest-timeout` | Automated tests | `pyproject.toml`, `test/AGENTS.md` |
| `markdownlint-cli2` | Markdown lint/fix | `.pre-commit-config.yaml`, `.markdownlint-cli2.yaml`, `.github/workflows/lint_md_all.yml` |
| `pre-commit` | Local hook orchestration | `pyproject.toml`, `.pre-commit-config.yaml` |
| `linkchecker` | Docs link validation | `pyproject.toml`, `.github/workflows/docs-build-check.yml` |

### 4) Key Commands

```bash
uv sync --dev
uv build
uv run pytest --tb=short
uv run pytest -m "" --tb=short
uv run black vultron/ test/
uv run flake8 vultron/ test/
uv run mypy
uv run pyright
uv run mkdocs build --config-file mkdocs.yml
```

### 5) Environment and Config

- Config sources: `config.example.yaml`, `vultron/config.py`, `.env.example`,
  `docker/.env.example`, `docker/docker-compose.yml`,
  `docker/docker-compose-multi-actor.yml`
- Required env vars verified in committed files:
  `VULTRON_CONFIG`, `VULTRON_MODE`, `VULTRON_SERVER__BASE_URL`,
  `VULTRON_SERVER__LOG_LEVEL`, `VULTRON_DATABASE__DB_URL`,
  `VULTRON_PRE_BOOTSTRAP_QUEUE_TIMEOUT_SECONDS`, `VULTRON_API_BASE_URL`,
  `VULTRON_ACTOR_ID`, `VULTRON_SEED_CONFIG`, `PROJECT_NAME`,
  `COMPOSE_PROJECT_NAME`, `DEMO`
- Deployment/runtime constraints: the main server uses SQLite by default, Docker
  runs `uvicorn vultron.adapters.driving.fastapi.main:app`, and the multi-actor
  compose stack allocates one SQLite-backed volume per actor service.

### 6) Evidence

- `pyproject.toml`
- `docker/Dockerfile`
- `.github/actions/setup-python-uv/action.yml`
- `.github/workflows/python-app.yml`
- `config.example.yaml`
- `vultron/config.py`
- `docs/reference/codebase/.codebase-scan.txt`
