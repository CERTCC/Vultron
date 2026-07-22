# Architecture

## Core Sections (Required)

### 1) Architectural Style

- **Primary style**: Hexagonal Architecture (Ports and Adapters) with an explicit wire-format layer
- **Why this classification**: Core domain logic is isolated behind Protocol-typed ports; driving adapters (HTTP/CLI/MCP) trigger use cases; driven adapters (SQLite, outbound HTTP delivery) implement outbound ports. Architecture-boundary tests enforce the dependency direction. Wire format (ActivityStreams 2.0) is treated as an adapter concern, not a domain dependency.
- **Primary constraints**:
  1. `vultron/core/` must not import from `vultron/adapters/` or `vultron/wire/` (enforced by `test/architecture/`)
  2. All external writes flow through `DataLayer.save()` — direct ORM mutations inside `execute()` are forbidden (ARCH-13)
  3. Use-case entry points follow `UseCase.__init__(dl, request)` + `execute() -> None` protocol; routing is table-driven via `USE_CASE_MAP`

### 2) System Flow

```text
HTTP POST /inbox  (wire: AS2 JSON)
  -> FastAPI inbox handler         [vultron/adapters/driving/fastapi/inbox_handler.py]
  -> AS2 parser (structural)       [vultron/wire/as2/parser.py]
  -> rehydrate()                   [vultron/wire/as2/rehydration.py]
  -> semantic extractor            [vultron/wire/as2/extractor/]
     (AS2 pattern -> MessageSemantics + VultronEvent)
  -> behavior dispatcher           [vultron/core/ports/dispatcher.py]
  -> USE_CASE_MAP lookup           [vultron/core/use_cases/]
  -> UseCase.execute()             [vultron/core/use_cases/received/]
     (may run BT sub-tree via py-trees)
  -> DataLayer.save()              [vultron/adapters/driven/datalayer_sqlite/]
  -> outbound delivery queue       [vultron/adapters/driven/prod_http_delivery.py]
  -> HTTP 202 Accepted             (background task via FastAPI BackgroundTasks)
```

### 3) Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|-----------------|------|--------------|----------|
| `vultron/core/` | Domain models, ports (Protocols), use cases, state enums, behavior trees, scoring | FastAPI, SQLModel, AS2 types | `notes/architecture-hexagonal.md`, `test/architecture/` |
| `vultron/wire/as2/` | AS2 vocabulary (Pydantic), parser, semantic extractor, activity factories | Core domain logic, FastAPI | `vultron/wire/as2/AGENTS.md` |
| `vultron/adapters/driving/` | HTTP routers, CLI, MCP server; triggers use cases | Business logic, persistence | `vultron/adapters/driving/fastapi/` |
| `vultron/adapters/driven/` | SQLite data layer (CRUD + queues), outbound HTTP delivery, sync adapter | Core domain rules | `vultron/adapters/driven/datalayer_sqlite/` |
| `vultron/adapters/connectors/` | Third-party tracker translations (Jira example, VINCE example) | Direct protocol handling | `vultron/adapters/connectors/` |
| `vultron/config/` | Settings models, YAML + env loading, `get_config()` | Adapter or core imports | `vultron/config/app.py`, `vultron/config/actor.py` |
| `vultron/bt/` | Behavior tree node library for CVD sub-protocols (EM, RM, CS, messaging) | Adapter imports | `vultron/bt/` |

### 4) Reused Patterns

| Pattern | Where found | Why it exists |
|---------|-------------|---------------|
| Port / Protocol | `vultron/core/ports/` | Decouple domain from adapter implementations; structural conformance without inheritance |
| Use-Case class (`UseCase` Protocol) | `vultron/core/use_cases/` | Encapsulate one business operation; consistent `__init__(dl, request) + execute()` contract |
| Table-driven dispatch (`USE_CASE_MAP`) | `vultron/core/ports/dispatcher.py` | Route inbound events to use cases without per-handler decorators |
| Behavior Tree node hierarchy | `vultron/bt/base/bt_node.py` + domain sub-trees | Encode CVD sub-protocol logic as composable, testable tree nodes |
| Factory function per object type | `vultron/wire/as2/factories/` | Construct outbound AS2 activities from domain objects in one place |
| Semantic pattern registry | `vultron/semantic_registry/` | Match incoming AS2 activities to `MessageSemantics` via ordered pattern list |
| Backward-compat shim (`datalayer_sqlite.py`) | `vultron/adapters/driven/datalayer_sqlite.py` | Re-export from split subpackage; callers do not update imports when internals split |
| `pydantic-settings` layered config | `vultron/config/app.py` | Merge YAML file + env vars + defaults in a single `AppConfig` object |

### 5) Known Architectural Risks

- **Architecture boundary tests fully passing**: `KNOWN_VIOLATIONS` is `frozenset()` in both `test_core_no_adapter_imports.py` and `test_core_no_wire_imports.py` — all prior violations have been resolved
- **State machine leakage via transitions library**: `vultron/core/states/` wraps `transitions`; coupling to a third-party state machine library in core
- **BT nodes hold mutable context via `blackboard`**: py-trees blackboard shared state can create implicit coupling between unrelated BT sub-trees
- **Demo layer mixed into `vultron/demo/`**: some demo code imports from adapters, which is appropriate, but the boundary between "demo" and "production use case" is not always clear

### 6) Evidence

- `notes/architecture-hexagonal.md`
- `AGENTS.md`
- `vultron/adapters/driving/fastapi/main.py`
- `vultron/core/ports/datalayer.py`
- `vultron/core/ports/use_case.py`
- `test/architecture/test_core_no_adapter_imports.py`
- `test/architecture/test_core_no_wire_imports.py`
