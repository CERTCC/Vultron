# Codebase Structure

## Core Sections (Required)

### 1) Top-Level Map

| Path | Purpose | Evidence |
|------|---------|----------|
| `vultron/` | Main Python package: adapters, core, wire layer, demos, metadata tooling | `docs/reference/codebase/.codebase-scan.txt`, `AGENTS.md` |
| `test/` | Pytest suite mirroring `vultron/` | `pyproject.toml`, `test/AGENTS.md` |
| `docs/` | MkDocs source for published/reference docs | `mkdocs.yml`, `docs/reference/codebase/.codebase-scan.txt` |
| `doc/` | Example and legacy-support docs outside MkDocs | `README.md`, `doc/README.md` |
| `notes/` | Durable design notes and architecture guidance | `notes/README.md` |
| `specs/` | Formal YAML requirement files and spec registry inputs | `specs/README.md` |
| `docker/` | Dockerfile, compose stacks, seed configs, and demo entrypoint | `docker/README.md`, `docker/Dockerfile` |
| `integration_tests/` | Manual Docker-backed acceptance scripts outside pytest | `integration_tests/README.md` |
| `.github/` | CI workflows, reusable actions, and repo automation | `.github/workflows/python-app.yml`, `.github/actions/setup-python-uv/action.yml` |
| `plan/` | Planning, history, and build-learning artifacts | `AGENTS.md`, `docs/reference/codebase/.codebase-scan.txt` |
| `site/` | Generated MkDocs output; not source | `docs/reference/codebase/.codebase-scan.txt` |
| `.venv/`, `.mypy_cache/`, `.pytest_cache/` | Local environment and tool caches; not source | `docs/reference/codebase/.codebase-scan.txt` |

### 2) Entry Points

- Main runtime entry: `vultron/adapters/driving/fastapi/main.py:app`
- Secondary entry points (worker/cli/jobs):
  `vultron/adapters/driving/fastapi/app.py:app_v2`,
  `vultron/adapters/driving/fastapi/app.py:create_app`,
  `vultron/demo/cli.py:main`, metadata CLIs under `[project.scripts]`, and
  MCP-style tool functions in `vultron/adapters/driving/mcp_server.py`
- How entry is selected (script/config): Docker runs
  `uvicorn vultron.adapters.driving.fastapi.main:app`; packaged CLI commands are
  declared under `[project.scripts]` in `pyproject.toml`; tests instantiate
  isolated apps via `create_app()`.

### 3) Module Boundaries

| Boundary | What belongs here | What must not be here |
|----------|-------------------|------------------------|
| `vultron/core/` | Domain models, ports, dispatcher, use cases, core BTs | FastAPI/framework imports and adapter-owned I/O |
| `vultron/wire/as2/` | ActivityStreams vocabulary, patterns, rehydration, extraction | Case/business logic |
| `vultron/adapters/driving/` | HTTP/CLI/MCP-facing translation into core calls | Persistent domain ownership |
| `vultron/adapters/driven/` | Persistence, outbound delivery, domain→wire translation adapters | Request routing and HTTP endpoint definitions |
| `vultron/metadata/` | Spec, notes, and history tooling | Runtime protocol orchestration |
| `vultron/demo/` | Demo orchestration, seeding, verification helpers | Authoritative domain interfaces |
| `vultron/bt/` | Legacy/experimental BT package retained alongside core behaviors | New adapter wiring or primary runtime entrypoints |
| `test/` | Mirrored tests and fixtures | Production runtime code |

### 4) Naming and Organization Rules

- File naming pattern: snake_case Python modules, e.g. `outbox_monitor.py`,
  `three_actor_demo.py`, `sync_activity_adapter.py`
- Directory organization pattern: layer-oriented runtime layout under
  `vultron/` (`core/`, `wire/`, `adapters/`) plus support packages
  (`demo/`, `metadata/`, `scripts/`)
- Import aliasing or path conventions: package-qualified absolute imports are
  the norm; selected façade/re-export modules exist, e.g.
  `vultron.adapters.driven.datalayer` and `vultron.wire.as2.extractor`

### 5) Evidence

- `docs/reference/codebase/.codebase-scan.txt`
- `pyproject.toml`
- `vultron/adapters/driving/fastapi/main.py`
- `vultron/adapters/driving/fastapi/app.py`
- `vultron/demo/cli.py`
- `docker/Dockerfile`
