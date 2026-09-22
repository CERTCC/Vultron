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
  -> FastAPI inbox handler         `vultron/adapters/driving/fastapi/inbox_handler.py`
  -> AS2 parser (structural)       `vultron/wire/as2/parser.py`
  -> rehydrate()                   `vultron/wire/as2/rehydration.py`
  -> semantic extractor            `vultron/wire/as2/extractor/`
     (AS2 pattern -> MessageSemantics + AnyReceivedEvent)
  -> behavior dispatcher           `vultron/core/ports/dispatcher.py`
  -> USE_CASE_MAP lookup           `vultron/core/use_cases/`
  -> UseCase.execute()             `vultron/core/use_cases/received/`
     (may run BT sub-tree via py-trees)
  -> DataLayer.save()              `vultron/adapters/driven/datalayer_sqlite/`
  -> outbound delivery             `vultron/adapters/driven/http_delivery.py`
                                   (`prod_http_delivery.py` is a NotImplementedError stub; demo uses `demo_http_delivery.py`)
  -> HTTP 202 Accepted             (background task via FastAPI BackgroundTasks)
```

### 3) Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|-----------------|------|--------------|----------|
| `vultron/core/` | Domain models, ports (Protocols), use cases, state enums, behavior trees, scoring | FastAPI, SQLModel, AS2 types | `notes/architecture-hexagonal.md`, `test/architecture/` |
| `vultron/core/predicates/` | Pure predicate functions (role checks, embargo eligibility, role-gated state invariants) — no I/O, no DataLayer | `behaviors/`, `services/`, `ports/` imports (cycle risk) | `notes/predicates-rule-layer.md` |
| `vultron/core/ports/wire_render.py` | `WireRenderPort` — driven port contract for rendering core objects to wire-shaped JSON | Core-to-wire import | `vultron/core/ports/wire_render.py` |
| `vultron/wire/as2/` | AS2 vocabulary (Pydantic), parser, semantic extractor, activity factories | Core domain logic, FastAPI | `vultron/wire/as2/AGENTS.md` |
| `vultron/adapters/driving/` | HTTP routers, CLI, MCP server; triggers use cases | Business logic, persistence | `vultron/adapters/driving/fastapi/` |
| `vultron/adapters/driven/` | SQLite data layer (CRUD + queues), outbound HTTP delivery, sync adapter, wire render adapter | Core domain rules | `vultron/adapters/driven/datalayer_sqlite/`, `vultron/adapters/driven/wire_render/` |
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
| `pydantic-settings` layered config | `vultron/config/app.py` | Merge YAML file + env vars + defaults in a single `AppConfig` object |
| Typed ports on BT DataLayer nodes | `vultron/core/behaviors/` (nodes using `WithPorts` variants) | Declare blackboard key dependencies as typed class attributes instead of calling `register_key()` at runtime; enforced by `test/architecture/test_no_bare_register_key_datalayer_nodes.py` (BTND-03-009) |
| `WireRenderPort` driven port | `vultron/core/ports/wire_render.py` + `vultron/adapters/driven/wire_render/as2.py` | Allows core behaviors to obtain wire-shaped (AS2 camelCase) JSON from a domain object without importing from `vultron/wire/`; adapter translates via `VOCABULARY` registry |

### 5) Known Architectural Risks

- **Core-boundary ratchets fully passing**: `KNOWN_VIOLATIONS` is `frozenset()` in both `test_core_no_adapter_imports.py` and `test_core_no_wire_imports.py` — all prior core-boundary violations resolved
- **Wire→core imports are governed by an allow-list, not a ratchet**: `test_wire_core_import_allowlist.py` enforces that wire MAY import `vultron/core/models/` and `vultron/core/states/`, and nothing else under `vultron/core/` (ARCH-22-001, ARCH-22-002 as amended by ADR-0099). `behaviors/`, `use_cases/`, `ports/`, `services/`, `predicates/`, `scoring/`, `participants/` and `case_states/` are forbidden. There is no violations inventory to read, because the previous prohibition on *all* wire→core imports was repealed: it is not among ADR-0009's six Key Rules, it inverts the inward dependency direction hexagonal architecture prescribes, and it was itself the cause of the duplicate `as_*` domain classes ADR-0099 removes. The substantive rule it was a poor proxy for is ARCH-01-003 — no handler, case or journal logic in wire. Migration epic: #2670
- **State machine leakage via transitions library**: `vultron/core/states/` wraps `transitions`; coupling to a third-party state machine library in core
- **BT nodes hold mutable context via `blackboard`**: py-trees blackboard shared state can create implicit coupling between unrelated BT sub-trees
- **Demo layer mixed into `vultron/demo/`**: some demo code imports from adapters, which is appropriate, but the boundary between "demo" and "production use case" is not always clear

### 6) Evidence

- `notes/architecture-hexagonal.md`
- `AGENTS.md`
- `specs/architecture.yaml` (ARCH spec group)
- `vultron/adapters/driving/fastapi/main.py`
- `vultron/core/ports/datalayer.py`
- `vultron/core/ports/use_case.py`
- `vultron/core/ports/wire_render.py`
- `vultron/adapters/driven/wire_render/as2.py`
- `test/architecture/test_core_no_adapter_imports.py`
- `test/architecture/test_core_no_wire_imports.py`
- `test/architecture/test_wire_core_import_allowlist.py`
- `test/architecture/test_no_bare_register_key_datalayer_nodes.py`
