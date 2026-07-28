# Codebase Structure

## Core Sections (Required)

### 1) Top-Level Map

| Path | Purpose | Evidence |
|------|---------|----------|
| `vultron/` | Main Python package — all production source | `pyproject.toml` `[tool.setuptools.packages.find]` |
| `vultron/core/` | Domain layer: models, ports, use cases, states, behaviors (py_trees BT nodes/trees) | `notes/architecture-hexagonal.md` |
| `vultron/wire/` | Wire format layer: AS2 vocabulary, parser, extractor, factories | `notes/architecture-hexagonal.md` |
| `vultron/adapters/` | Adapter layer: driving (HTTP/CLI/MCP), driven (SQLite, delivery), connectors | `notes/architecture-hexagonal.md` |
| `vultron/bt/` | **Simulation** BT node library (custom engine, not py_trees); grouped by CVD domain area. MUST NOT be merged with prototype BTs in `vultron/core/behaviors/` | `vultron/bt/` directory listing, `notes/bt-integration.md` |
| `vultron/config/` | Layer-neutral configuration models and loading logic | `vultron/config/app.py`, `vultron/config/actor.py` |
| `vultron/enums/` | Shared CVD-domain enums (roles, states) imported by config and core | `vultron/enums/` |
| `vultron/demo/` | Demo scenario runners and seed-config helpers | `pyproject.toml` entry points |
| `vultron/metadata/` | Spec registry, history CLI, notes metadata tooling | `vultron/metadata/specs/`, `vultron/metadata/history/` |
| `vultron/scripts/` | CLI entry points (`vultrabot`) | `pyproject.toml` `[project.scripts]` |
| `vultron/semantic_registry/` | Consolidated semantic dispatch registry (`SEMANTIC_REGISTRY`, `extract_event`, `use_case_map`) — neutral layer importable by wire, core, adapter, and test code | `vultron/semantic_registry/__init__.py` |
| `test/` | Pytest test suite (mirrors `vultron/` layout) | `pyproject.toml` `[tool.pytest.ini_options]` |
| `test/architecture/` | Architecture-boundary enforcement tests | `test/architecture/test_core_no_adapter_imports.py` |
| `specs/` | Structured YAML specification files | `specs/README.md` |
| `notes/` | Durable design insight Markdown files | `notes/README.md` |
| `docs/` | MkDocs documentation source | `Makefile` `docs` target |
| `plan/` | Agent workflow files: implementation plan, priorities, learnings, history | `plan/BUILD_LEARNINGS.md`, `plan/IMPLEMENTATION_PLAN.md` |
| `.github/workflows/` | CI/CD pipeline definitions | `.github/workflows/python-app.yml` |
| `.devcontainer/` | Dev container configuration | `.devcontainer/Dockerfile` |
| `integration_tests/` | Separate integration test suite | `integration_tests/README.md` |

### 2) Entry Points

- **Main ASGI app** (uvicorn/production): `vultron.adapters.driving.fastapi.main:app`
- **Sub-app for dev/tests**: `vultron.adapters.driving.fastapi.app:app_v2`
- **Inbox routes** (actor-scoped): `vultron/adapters/driving/fastapi/routers/actors/_routes.py` (package; `_routes.py` defines POST /inbox)
- **CLI scripts**:
  - `vultron-demo` → `vultron.demo.cli:main`
  - `vultrabot` → `vultron.scripts.vultrabot:main`
  - `vultrabot_cvd` → `vultron.demo.vultrabot:main`
  - `spec-dump` / `spec-dump-llm-json` → `vultron.metadata.specs.render:main_llm_json`
  - `spec-lint` → `vultron.metadata.specs.lint:main`
  - `append-history` → `vultron.metadata.history.cli:main`
  - `show-history` → `vultron.metadata.history.show_history_cli:main`
- **How entry is selected**: via `[project.scripts]` in `pyproject.toml`; uvicorn deployment uses `vultron.adapters.driving.fastapi.main:app`

### 3) Module Boundaries

| Boundary | What belongs here | What must not be here |
|----------|-------------------|------------------------|
| `vultron/core/` | Domain models, ports (Protocol classes), use cases, states, py_trees BT nodes/trees (`core/behaviors/`) | FastAPI, wire-format (AS2), adapter imports |
| `vultron/wire/as2/` | AS2 vocabulary (Pydantic models), parser, semantic extractor (`extractor/`), factories | Core domain import of AS2 types; FastAPI |
| `vultron/semantic_registry/` | `SEMANTIC_REGISTRY` ordered list, `SemanticEntry` dataclass, `extract_event`, `use_case_map`, `_validate_registry_order` | Pattern definitions (those live in `extractor/_instances.py`) |
| `vultron/adapters/` | HTTP handlers, SQLite data layer, outbound delivery, CLI, MCP, connectors | Core domain logic (no business rules) |
| `vultron/config/` | Configuration models and loading only | Imports from `vultron.adapters` or `vultron.core` |
| `vultron/enums/` | Shared CVD enums usable by `config/` and `core/` | Adapter or wire-specific types |
| `vultron/bt/` | Simulation BT node definitions (custom engine) for CVD sub-protocols | Direct FastAPI or SQLite imports; MUST NOT use `py_trees` |

Enforced by: `test/architecture/test_core_no_adapter_imports.py`, `test/architecture/test_core_no_wire_imports.py`

### 4) Naming and Organization Rules

- **File naming**: `snake_case.py` for modules (e.g., `bt_node.py`, `datalayer_sqlite.py`)
- **Class naming**: `PascalCase`; wire-layer AS2 vocab classes use `as_` prefix (e.g., `as_VulnerabilityCase`, `as_Activity`)
- **Domain abbreviation**: `vul` (not `vuln`) for vulnerability; `em` for embargo management; `rm` for report management; `cs` for case state
- **Use-case naming**: `Svc` prefix + domain noun + action suffix (e.g., `SvcCloseReportUseCase`)
- **Directory organization**: by architectural layer (`core/`, `wire/`, `adapters/`) then by CVD domain area within layers
- **Import conventions**: absolute imports; no circular dependencies; core must not import from adapters or wire; `__init__.py` re-exports for backward compatibility

### 5) Evidence

- `vultron/` directory listing
- `pyproject.toml` `[project.scripts]`
- `notes/architecture-hexagonal.md`
- `AGENTS.md`
- `test/architecture/test_core_no_adapter_imports.py`
