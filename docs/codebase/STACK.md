# Technology Stack

## Core Sections (Required)

### 1) Runtime Summary

| Area | Value | Evidence |
|------|-------|----------|
| Primary language | Python 3.12+ | `pyproject.toml` `requires-python = ">=3.12"` |
| Runtime version (CI) | Python 3.13 | `.github/actions/setup-python-uv/action.yml` (default: `"3.13"`) |
| Package manager | uv | `Makefile`, `uv.lock` |
| Build system | setuptools + setuptools-scm | `pyproject.toml` `[build-system]` |
| Version source | git tags (semver `v<N>.*`) | `pyproject.toml` `[tool.setuptools_scm]` |

### 2) Production Frameworks and Dependencies

| Dependency | Version | Role in system | Evidence |
|------------|---------|----------------|----------|
| FastAPI | >=0.139.2 | HTTP API server (driving adapter) | `pyproject.toml` |
| Pydantic v2 | ==2.13.4 | Data validation; domain + wire models | `pyproject.toml` |
| pydantic-settings | >=2.14.2 | Layered settings (env, YAML, defaults) | `pyproject.toml` |
| SQLModel | >=0.0.39 | SQLite-backed data layer (ORM/schema) | `pyproject.toml` |
| uvicorn | >=0.51.0 | ASGI server for FastAPI | `pyproject.toml` |
| py-trees | >=2.5.0 | Behavior tree execution engine | `pyproject.toml` |
| networkx | >=3.5 | Graph operations for BT and case analysis | `pyproject.toml` |
| transitions | >=0.9.3 | State machine definitions | `pyproject.toml` |
| PyYAML | >=6.0 | YAML config + spec file parsing | `pyproject.toml` |
| python-frontmatter | >=1.3.0 | YAML frontmatter in Markdown notes | `pyproject.toml` |
| rdflib + owlready2 | >=7.2.1 / >=0.51 | Semantic/ontology support | `pyproject.toml` |
| scipy + pandas | >=1.18.0 / >=3.0.3 | Analysis and scoring | `pyproject.toml` |
| mkdocs-material | >=9.6.20 | Documentation site generation | `pyproject.toml` |
| click | >=8.4.2 | CLI entry points | `pyproject.toml` |
| httpx2 | latest | HTTP client for outbound delivery | `pyproject.toml` |

### 3) Development Toolchain

| Tool | Purpose | Evidence |
|------|---------|----------|
| black | Code formatter (line-length 79) | `pyproject.toml` `[tool.black]`, `[dependency-groups].dev` |
| flake8 | Linter (E203/E501 ignored, max complexity 10) | `.flake8`, `[dependency-groups].dev` |
| mypy | Static type checking (>=2.3.0) | `pyproject.toml` `[dependency-groups].dev` |
| pyright | Static type checking (>=1.1.411, second pass) | `pyrightconfig.json`, `[dependency-groups].dev` |
| isort | Import ordering (black profile, >=7.0.0) | `pyproject.toml` `[tool.isort]` |
| pre-commit | Git hook runner | `[dependency-groups].dev` |
| pytest | Test runner (>=9.1.1) | `pyproject.toml` `[dependency-groups].dev` |
| pytest-timeout | Per-test timeout (5 s default, thread method) | `pyproject.toml` `[tool.pytest.ini_options]` |
| pytest-xdist | Parallel test execution (>=3.8.0) | `[dependency-groups].dev` |
| markdownlint-cli2 | Markdown linting | `mdlint.sh`, `Makefile` |
| linkchecker | Link validation for docs | `[dependency-groups].dev` |

### 4) Key Commands

```bash
# Install all deps (including dev)
uv sync --dev

# Run unit tests (default — integration tests excluded)
uv run pytest --tb=short

# Run ALL tests (unit + integration)
uv run pytest -m "" --tb=short

# Format code
uv run black .

# Lint
uv run flake8 vultron/ test/
uv run mypy
uv run pyright

# Build package
uv build

# Serve docs locally
uv run mkdocs serve

# Export spec registry as LLM-friendly JSON
uv run spec-dump
```

### 5) Environment and Config

- Config sources: `VULTRON_CONFIG` env var → YAML file (default `config.yaml`), then environment variables, then Pydantic defaults
- Required env vars:
  - `PROJECT_NAME` (default: `vultron`) — from `.env.example`
  - `VULTRON_CONFIG` — path to YAML config file (optional; defaults to `config.yaml`)
  - `VULTRON_DATABASE__DB_URL` — SQLite URL (default: file-based; tests override to `sqlite:///:memory:`)
- Deployment/runtime constraints: Python 3.12+; runs via uvicorn as ASGI app; `VULTRON_CONFIG` must point to a valid file if set

### 6) Evidence

- `pyproject.toml`
- `uv.lock`
- `.flake8`
- `.env.example`
- `.github/workflows/python-app.yml`
- `Makefile`
