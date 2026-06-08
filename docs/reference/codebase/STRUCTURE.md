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
- Sub-application/app-factory entries:
  `vultron/adapters/driving/fastapi/app.py:app_v2` and
  `vultron/adapters/driving/fastapi/app.py:create_app`
- CLI/tool entry points: `vultron/demo/cli.py:main`,
  `vultron/scripts/vultrabot.py:main`, and metadata/spec-history CLIs declared
  under `[project.scripts]` in `pyproject.toml`
- MCP trigger surface: tool functions in
  `vultron/adapters/driving/mcp_server.py`
- How entry is selected (script/config): Docker runs
  `uvicorn vultron.adapters.driving.fastapi.main:app`; packaged CLI entry
  points are declared under `[project.scripts]` in `pyproject.toml`.

### 3) Module Boundaries

| Boundary | What belongs here | What must not be here |
|----------|-------------------|------------------------|
| `vultron/core/` | Domain models, ports, dispatch, use cases, core behavior trees | FastAPI imports, adapter types, direct AS2 parsing |
| `vultron/wire/` | AS2 parsing, vocabulary, semantic extraction, rehydration | Case-handling business logic |
| `vultron/adapters/driving/` | HTTP/MCP-facing translation into core calls | Persistent domain state ownership |
| `vultron/adapters/driven/` | Persistence, outbound delivery, and domain→wire activity translation | Framework-facing request handling |
| `vultron/metadata/` | Spec, note, and history tooling plus CLI entry points | Runtime protocol behavior |
| `vultron/scripts/` | Standalone CLI scripts such as `vultrabot` wrappers and ontology tooling | Core domain logic |
| `vultron/demo/` | Demo orchestration, exchange scripts, and scenario verification helpers | Authoritative domain interfaces |
| `vultron/bt/` | Legacy and experimental behavior-tree packages still shipped with the repo | FastAPI adapters or new core use-case orchestration |
| `test/` | Mirrored test modules and fixture layers | Production runtime code |

Notable adapter files added since last scan:

- `vultron/adapters/driven/sync_activity_adapter.py` — implements `SyncActivityPort`; sole domain→wire translation point for sync-related activities (ARCH-01-001)
- `vultron/adapters/driven/trigger_activity_adapter.py` — implements `TriggerActivityPort`; sole domain→wire translation point for trigger-originated activities
- `vultron/adapters/driven/prod_http_delivery.py` — **stub** for future signed HTTP delivery to remote inboxes
- `vultron/adapters/driving/shared_inbox.py` — **stub** for ActivityPub shared-inbox fan-out

### 4) Naming and Organization Rules

- File naming pattern: snake_case Python modules, for example
  `datalayer_sqlite.py`, `outbox_monitor.py`, `three_actor_demo.py`
- Directory organization pattern: the canonical runtime layout under
  `vultron/` is `adapters/`, `core/`, `wire/`, `demo/`, `metadata/`, and
  `scripts/`; legacy BT packages remain under `bt/` alongside
  `core/behaviors/`
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
