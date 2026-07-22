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
  -> inbox BT pipeline             [vultron/core/behaviors/inbox/inbox_tree.py]
     (parse → rehydrate → extract semantics → defer-check → dispatch → outcome)
  -> semantic extractor            [vultron/wire/as2/extractor/]
     (AS2 pattern -> MessageSemantics + VultronEvent via SEMANTIC_REGISTRY)
  -> dispatcher                    [vultron/core/dispatcher.py]
     (DirectActivityDispatcher; port: vultron/core/ports/dispatcher.py)
  -> SEMANTIC_REGISTRY lookup      [vultron/semantic_registry/]
     (SemanticEntry: pattern + event_class + use_case_class + wire_activity_class)
  -> UseCase.execute()             [vultron/core/use_cases/received/]
     (may run BT sub-tree via py-trees through BTBridge)
  -> DataLayer.save()              [vultron/adapters/driven/datalayer_sqlite/]
     (auto-rehydrates nested object refs on dl.read(); CORE_VOCABULARY for typed return)
  -> outbound delivery queue       [vultron/adapters/driven/prod_http_delivery.py]
  -> HTTP 202 Accepted             (background task via FastAPI BackgroundTasks)
```

### 3) Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|-----------------|------|--------------|----------|
| `vultron/core/` | Domain models, ports (Protocols), use cases, state enums, py_trees BT nodes/trees (`core/behaviors/`), scoring | FastAPI, SQLModel, AS2 types | `notes/architecture-hexagonal.md`, `test/architecture/` |
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
| Semantic registry (`SEMANTIC_REGISTRY`) | `vultron/semantic_registry/` | Single source of truth mapping `MessageSemantics` to pattern + event class + use-case class; order-sensitive (specific before general); validated at import time by `_validate_registry_order()` |
| Table-driven dispatch (`DirectActivityDispatcher`) | `vultron/core/dispatcher.py` + port: `vultron/core/ports/dispatcher.py` | Route inbound events to use cases via `SEMANTIC_REGISTRY`; raises `VultronApiHandlerNotFoundError` for unrecognised types |
| Simulation BT node hierarchy | `vultron/bt/base/bt_node.py` + domain sub-trees | Custom BT engine for simulation; MUST NOT be merged with prototype BTs in `core/behaviors/` |
| Prototype BT node library (`py_trees`) | `vultron/core/behaviors/` + domain sub-trees | py_trees-based BTs for prototype handler workflows; each `MessageSemantics` type has a focused tree |
| Inbox BT pipeline | `vultron/core/behaviors/inbox/inbox_tree.py` | Enforces fixed parse → rehydrate → extract → defer-check → dispatch → outcome sequence |
| BTBridge | `vultron/core/behaviors/bridge.py` | Handler-to-BT execution interface: setup blackboard, execute tree, capture result; serialises concurrent BT executions with a lock |
| Factory function per object type | `vultron/wire/as2/factories/` | Construct outbound AS2 activities from domain objects in one place; use `wire_cls.from_core()` — never `model_dump()` + `model_validate()` |
| DataLayer auto-rehydration | `vultron/adapters/driven/datalayer_sqlite/datalayer.py` | `dl.read()` reconstructs fully typed domain objects via `CORE_VOCABULARY`; expands dehydrated `object_`/`target`/list-ref fields |
| `CasePersistence` / `DataLayer` split | `vultron/core/ports/case_persistence.py`, `vultron/core/ports/datalayer.py` | Narrow core-facing port (`CasePersistence`) vs. full adapter port (`DataLayer`); `ActorScopedDataLayer` adds inbox/outbox queue methods |
| Backward-compat shim (`datalayer_sqlite.py`) | `vultron/adapters/driven/datalayer_sqlite.py` | Re-export from split subpackage; callers do not update imports when internals split |
| `pydantic-settings` layered config | `vultron/config/app.py` | Merge YAML file + env vars + defaults in a single `AppConfig` object |

### 5) Known Architectural Risks

- **Architecture boundary tests fully passing**: `KNOWN_VIOLATIONS` is `frozenset()` in both `test_core_no_adapter_imports.py` and `test_core_no_wire_imports.py` — all prior violations have been resolved
- **State machine leakage via transitions library**: `vultron/core/states/` wraps `transitions`; coupling to a third-party state machine library in core
- **py_trees process-global blackboard**: `py_trees.blackboard.Blackboard.storage` is global; BT bridge serialises concurrent executions with a threading lock; tests MUST clear `Blackboard.storage` between BT tests
- **Dual BT engine coexistence**: `vultron/bt/` (simulation, custom engine) and `vultron/core/behaviors/` (prototype, py_trees) MUST NOT be merged; they serve different purposes
- **Demo layer mixed into `vultron/demo/`**: some demo code imports from adapters, which is appropriate, but the boundary between "demo" and "production use case" is not always clear
- **`CaseOutboxPersistence` smell marker**: a `ReceivedUseCase` depending on `CaseOutboxPersistence` mixes inbound processing with outbound broadcast; review for cleaner split

### 6) Evidence

- `notes/architecture-hexagonal.md`
- `AGENTS.md`
- `vultron/adapters/driving/fastapi/main.py`
- `vultron/core/ports/datalayer.py`
- `vultron/core/ports/case_persistence.py`
- `vultron/core/ports/use_case.py`
- `vultron/core/dispatcher.py`
- `vultron/core/behaviors/bridge.py`
- `vultron/core/behaviors/inbox/inbox_tree.py`
- `vultron/semantic_registry/__init__.py`
- `notes/datalayer-design.md`
- `test/architecture/test_core_no_adapter_imports.py`
- `test/architecture/test_core_no_wire_imports.py`
