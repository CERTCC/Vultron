# Codebase Structure

## Core Sections (Required)

### 1) Top-Level Map

| Path | Purpose | Evidence |
|------|---------|----------|
| `vultron/` | Main application package: adapters, core logic, wire models, demos, metadata tooling | `AGENTS.md`, `docs/reference/codebase/.codebase-scan.txt` |
| `test/` | Pytest suite mirroring `vultron/` | `test/AGENTS.md`, `pyproject.toml` |
| `docs/` | MkDocs source for published documentation site | `mkdocs.yml`, `docs/reference/codebase/.codebase-scan.txt` |
| `doc/` | Example and legacy supporting docs distinct from MkDocs site | `README.md`, `doc/README.md` |
| `notes/` | Durable design notes and architecture guidance | `notes/README.md`, `AGENTS.md` |
| `specs/` | Formal requirement files and spec tooling inputs | `specs/README.md` |
| `docker/` | Dockerfiles, compose stacks, and seed configs for demos | `docker/README.md`, `docker/docker-compose.yml` |
| `integration_tests/` | Manual acceptance/integration scripts outside pytest | `integration_tests/README.md` |
| `plan/` | Priorities, history, and implementation planning artifacts | `docs/reference/codebase/.codebase-scan.txt`, `AGENTS.md` |
| `.github/` | CI workflows, repo automation, and authoring instructions | `.github/workflows/python-app.yml`, `.github/dependabot.yml` |

### 2) Entry Points

- Main runtime entry: `vultron/adapters/driving/fastapi/main.py:app`
- Secondary entry points (worker/cli/jobs): `vultron/adapters/driving/fastapi/app.py:app_v2`,
  `vultron/demo/cli.py:main`, MCP adapter functions in
  `vultron/adapters/driving/mcp_server.py`
- How entry is selected (script/config): Docker runs
  `uvicorn vultron.adapters.driving.fastapi.main:app`; CLI entry points are
  declared under `[project.scripts]` in `pyproject.toml`.

### 3) Module Boundaries

| Boundary | What belongs here | What must not be here |
|----------|-------------------|------------------------|
| `vultron/core/` | Domain models, ports, dispatch, use cases, behavior trees | FastAPI imports, adapter types, direct AS2 parsing |
| `vultron/wire/` | AS2 parsing, vocabulary, semantic extraction, rehydration | Case-handling business logic |
| `vultron/adapters/driving/` | HTTP/MCP-facing translation into core calls | Persistent domain state ownership |
| `vultron/adapters/driven/` | Persistence and outbound delivery implementations | Framework-facing request handling |
| `vultron/demo/` | CLI demos and workflow scripts | Authoritative domain interfaces |
| `test/` | Mirrored test modules and fixture layers | Production runtime code |

### 4) Naming and Organization Rules

- File naming pattern: snake_case Python modules, for example
  `datalayer_sqlite.py`, `outbox_monitor.py`, `three_actor_demo.py`
- Directory organization pattern: primarily layer/domain based
  (`core/`, `wire/`, `adapters/`, `demo/`, `metadata/`)
- Import aliasing or path conventions: package-qualified imports dominate;
  thin re-export modules exist for convenience, for example
  `vultron.adapters.driven.datalayer` and
  `vultron.adapters.driving.fastapi.routers.__init__`.

### 5) Evidence

- `docs/reference/codebase/.codebase-scan.txt`
- `pyproject.toml`
- `docker/Dockerfile`
- `AGENTS.md`
- `test/AGENTS.md`
- `vultron/adapters/driving/fastapi/main.py`
