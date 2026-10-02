---
stakeholder_type: [project-contributor]
---

# Technology Stack

## Core Sections (Required)

### 1) Runtime Summary

| Area | Value | Evidence |
|------|-------|----------|
| Primary language | Python 3.12+ | `pyproject.toml` `requires-python = ">=3.12"` |
| Runtime version (CI) | Python 3.13 | `.github/actions/setup-python-uv/action.yml` (default: `"3.13"`) |
| Package manager | uv (CI syncs with `--dev --frozen`) | `Makefile`, `uv.lock`, `.github/actions/setup-python-uv/action.yml` |
| Build system | setuptools + setuptools-scm | `pyproject.toml` `[build-system]` |
| Version source | git tags, three-component `N.N.N` with optional `v` prefix and no pre-release suffix (ADR-0006); `git describe` matches `v[0-9]*`; fallback `0.0.0+dev`; written to `vultron/_version.py` | `pyproject.toml` `[tool.setuptools_scm]` |

### 2) Production Frameworks and Dependencies

| Dependency | Version | Role in system | Evidence |
|------------|---------|----------------|----------|
| FastAPI | >=0.141.1 | HTTP API server (driving adapter) | `pyproject.toml` |
| Pydantic v2 | ==2.13.5 | Data validation; domain + wire models | `pyproject.toml` |
| pydantic-settings | >=2.15.0 | Layered settings (YAML, env, defaults) | `pyproject.toml`, `vultron/config/app.py` |
| SQLModel | >=0.0.39 | SQLite-backed data layer (ORM/schema) | `pyproject.toml` |
| uvicorn | >=0.52.3 | ASGI server for FastAPI | `pyproject.toml`, `docker/Dockerfile` |
| py-trees | >=2.6.0 | Behavior tree engine for `vultron/core/behaviors/` | `pyproject.toml` |
| networkx | >=3.5 | Graphs in the legacy BT simulator, the case-state hypercube and the spec registry | `vultron/bt/base/bt_node.py`, `vultron/core/case_states/hypercube.py`, `vultron/metadata/specs/registry.py` |
| transitions | >=0.9.3 | State machine definitions (EM, RM, CS, PEC) | `vultron/core/states/` |
| pandas | >=3.0.5 | Tabular case-state analysis and the legacy simulator demo | `vultron/core/case_states/hypercube.py`, `vultron/bt/base/demo/cvd.py` |
| scipy | >=1.18.0 | Declared, but no module in `vultron/` or `test/` imports it (see `CONCERNS.md`) | `pyproject.toml` |
| PyYAML | >=6.0 | YAML config + spec file parsing | `pyproject.toml` |
| python-frontmatter | >=1.3.0 | YAML frontmatter in Markdown notes, ADRs and docs pages | `vultron/metadata/` |
| pathspec | >=0.12.1 | Glob matching for docs page-schema and What's New tooling | `vultron/metadata/docs/page_schema.py`, `vultron/metadata/docs/whats_new.py` |
| isodate | >=0.7.2 | ISO 8601 duration/date parsing | `pyproject.toml` |
| click | >=8.4.2 | CLI entry points | `vultron/demo/cli.py` |
| httpx2 | unpinned (`uv.lock` resolves the version) | Async HTTP client for outbound delivery, imported as `httpx` | `vultron/adapters/driven/http_delivery.py` |
| mkdocs + mkdocs-material | >=1.6.1 / >=9.7.7 | Documentation site generation | `pyproject.toml`, `mkdocs.yml` |
| mkdocs plugins | `mkdocstrings`, `mkdocstrings-python`, `griffelib`, `mkdocs-autorefs`, `mkdocs-include-markdown-plugin`, `mkdocs-redirects`, `mkdocs-print-site-plugin`, `mkdocs-material-extensions`, `markdown-exec` | API docs, include fragments, redirects, executable blocks | `pyproject.toml`, `mkdocs.yml` |

The docs toolchain is declared as a production dependency, not a dev group.

### 3) Development Toolchain

| Tool | Purpose | Evidence |
|------|---------|----------|
| ruff | Linter, formatter and import sorter (>=0.16.9; line-length 79, max complexity 10; ADR-0094). Replaced black, flake8 and isort; scope is declared in `[tool.ruff]`, so every caller runs it bare | `pyproject.toml` `[tool.ruff]`, `[dependency-groups].dev` |
| mypy | Static type checking (>=2.3.0) over `vultron` and `test` | `.mypy.ini`, `[dependency-groups].dev` |
| pyright | Static type checking (>=1.1.411, `basic` mode, second pass) over `vultron` and `test` | `pyrightconfig.json`, `[dependency-groups].dev` |
| pre-commit | Git hook runner (>=4.6.2); hooks include codespell, actionlint, markdownlint-cli2, frontmatter validators, generated-artifact sync checks, ruff and spec-lint | `.pre-commit-config.yaml`, `[dependency-groups].dev` |
| codespell | Spelling floor for docs (en-GB to en-US only) | `pyproject.toml` `[tool.codespell]`, `.pre-commit-config.yaml` |
| pytest | Test runner (>=9.1.1) | `pyproject.toml` `[dependency-groups].dev` |
| pytest-timeout | Per-test timeout (30 s unit tier, raised from 5 s in #2270; 60 s integration tier) | `pyproject.toml` `[tool.pytest.ini_options]`, `test/conftest.py` |
| pytest-xdist | Parallel test execution (>=3.8.0) | `[dependency-groups].dev` |
| pandas-stubs / types-networkx / types-pyyaml | Type stubs for third-party deps | `[dependency-groups].dev` |
| graphifyy | Codebase knowledge-graph tooling (>=0.9.43) | `[dependency-groups].dev` |
| markdownlint-cli2 | Markdown linting (not a Python dependency) | `mdlint.sh`, `.markdownlint-cli2.yaml`, `Makefile` |

### 4) Key Commands

```bash
# Install all deps (including dev)
uv sync --dev

# Run unit tests (default — integration tests excluded)
uv run pytest --tb=short

# Run ALL tests (unit + integration) — what CI's test job runs
uv run pytest -m "" --tb=short

# Format and lint (ruff takes no path arguments)
uv run ruff format
uv run ruff check

# Type-check
uv run mypy
uv run pyright

# Build package
uv build

# Serve docs locally
uv run mkdocs serve

# Spec registry: map first, then targeted LLM-friendly JSON
PYTHONPATH= uv run spec-dump --index
PYTHONPATH= uv run spec-dump --topic CS --text
```

### 5) Environment and Config

- Config sources, in precedence order: the YAML file named by `VULTRON_CONFIG` (default `config.yaml`), then `VULTRON_`-prefixed environment variables with `__` as the nested delimiter, then Pydantic defaults.
  `config.example.yaml` is the committed example.
- Environment variables documented in `vultron/config/__init__.py`:
  - `VULTRON_CONFIG` — path to the YAML config file; a set-but-missing path raises an error.
  - `VULTRON_SERVER__BASE_URL`, `VULTRON_SERVER__LOG_LEVEL` — server settings.
  - `VULTRON_DATABASE__DB_URL` — SQLite URL (tests force `sqlite:///:memory:`).
  - `VULTRON_MODE` — runtime mode.
  - `VULTRON_LEDGER__CLOCK_SKEW_TOLERANCE_SECONDS`, `VULTRON_LEDGER__FUTURE_TOLERANCE_SECONDS`, `VULTRON_LEDGER__STALENESS_WINDOW_DAYS` — ledger timestamp tolerances (`vultron/config/ledger.py`).
- `.env.example` documents only `PROJECT_NAME` (default `vultron`), which the Docker Compose files use for image names.
- Deployment/runtime constraints: Python 3.12+; runs via uvicorn as the ASGI app `vultron.adapters.driving.fastapi.main:app`.
- Containerized multi-actor demo: `docker/docker-compose.yml` and `docker/docker-compose-multi-actor.yml` (single Dockerfile at `docker/Dockerfile`, entrypoint `docker/demo-entrypoint.sh`, seed configs under `docker/seed-configs/`), used by the `demo-integration.yml` CI workflow.
  The codebase scan's "No containerization configs detected" is a false negative, because it does not scan the `docker/` subdirectory.

### 6) Evidence

- `pyproject.toml`
- `uv.lock`
- `.mypy.ini`
- `pyrightconfig.json`
- `.pre-commit-config.yaml`
- `.env.example`
- `config.example.yaml`
- `vultron/config/__init__.py`
- `vultron/config/app.py`
- `.github/actions/setup-python-uv/action.yml`
- `.github/workflows/python-app.yml`
- `docker/Dockerfile`
- `Makefile`
