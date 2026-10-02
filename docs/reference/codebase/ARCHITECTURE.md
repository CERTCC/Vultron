---
stakeholder_type: [project-contributor]
---

# Architecture

## Core Sections (Required)

### 1) Architectural Style

- **Primary style**: Hexagonal Architecture (Ports and Adapters) with an explicit wire-format layer
- **Why this classification**: Core domain logic is isolated behind Protocol-typed ports.
  Driving adapters (FastAPI HTTP routes, the CLI) call into the core through dispatcher ports; driven adapters (SQLite, outbound HTTP delivery, wire rendering, trigger-activity construction) implement outbound ports.
  Architecture-boundary tests enforce the dependency direction.
  Wire format (ActivityStreams 2.0) is a serialization of the one core object model (ADR-0099), not a domain dependency.
- **Primary constraints**:
  1. `vultron/core/` must not import from `vultron/adapters/`, `vultron/wire/` or `vultron/demo/` (enforced by `test/architecture/`)
  2. A use case's `execute()` must not call `dl.save/create/update/delete()`, directly or through a helper; DataLayer mutations happen in BT leaf nodes run through `BTBridge` so they pass the audit trail and ledger commit (BT-06-001, BT-15-001, CLP-10-020; ratchet `test_no_dl_mutations_in_execute.py`)
  3. Use-case entry points follow `UseCase.__init__(dl, request)` + `execute()`.
     Received use cases return `HandlerResult` (ADR-0095); trigger use cases return their verb's `TriggerResult` subtype (ADR-0110); both live in `vultron/core/models/use_case_result.py`.
     Routing is table-driven on both sides: `use_case_map()` in `vultron/semantic_registry/` for received activities, `TRIGGER_REGISTRY` in `vultron/trigger_registry/` for trigger verbs.
  4. Every received-side tree is built by `create_receive_activity_tree()` in the order intake → guards → commit → effects (ADR-0111, CLP-10-006)

### 2) System Flow

Received activity (inbox):

```text
HTTP POST /actors/{actor_id}/inbox  (wire: AS2 JSON)
  -> inbox route                   `vultron/adapters/driving/fastapi/routers/actors/_routes.py`
  -> parse_activity (structural)   `vultron/wire/as2/parser.py`
     + unknown-key disposition     `vultron/wire/as2/unknown_keys.py`
  -> HTTP 202 Accepted; work continues in a BackgroundTasks task
  -> inbox orchestration           `vultron/adapters/driving/fastapi/inbox_orchestration.py`
     (BT work runs in a worker thread via asyncio.to_thread, IE-06-003)
  -> rehydrate()                   `vultron/wire/as2/rehydration.py`
  -> semantic extraction           `vultron/wire/as2/extractor/`
     (AS2 pattern -> MessageSemantics + VultronEvent)
  -> dispatcher                    `vultron/core/dispatcher.py` (port: `vultron/core/ports/dispatcher.py`)
  -> use_case_map() lookup         `vultron/semantic_registry/`
  -> *ReceivedUseCase.execute()    `vultron/core/use_cases/received/`
  -> BTBridge runs the received tree  `vultron/core/behaviors/bridge.py`
     intake -> guards -> commit -> effects; nodes write through DataLayer
  -> DataLayer                     `vultron/adapters/driven/datalayer_sqlite/` (one store per actor, ADR-0073)
  -> outbox handler + lanes        `vultron/adapters/driving/fastapi/outbox_handler.py`, `outbox_lanes.py`
     (sealed body relayed as stored; per-recipient order, ADR-0112)
  -> outbound delivery             `vultron/adapters/driven/http_delivery.py`
     (`prod_http_delivery.py` is a NotImplementedError stub; demo uses `demo_http_delivery.py`)
```

Trigger (actor-initiated action):

```text
HTTP POST /actors/{actor_id}/trigger/{verb}  (or /actors/{actor_id}/demo/{verb} for demo-only verbs)
  -> trigger router                `vultron/adapters/driving/fastapi/routers/trigger_*.py`, `demo_triggers.py`
  -> run_trigger()                 `vultron/adapters/driving/fastapi/trigger_runner.py`
  -> TriggerDispatcher port        `vultron/core/ports/trigger_dispatcher.py`
  -> RegistryTriggerDispatcher     `vultron/core/trigger_dispatcher.py` (row from `TRIGGER_REGISTRY`)
  -> Svc*UseCase.execute()         `vultron/core/use_cases/triggers/` (BT-backed via `SvcBTTriggerBase`)
  -> TriggerResult subtype -> response model; outbox drain of the emitting actor scheduled
```

The `OutboxMonitor` in `vultron/adapters/driving/fastapi/outbox_monitor.py` also drains registered actor outboxes in a background loop.

### 3) Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|-----------------|------|--------------|----------|
| `vultron/core/` | Domain models, ports (Protocols), use cases, state enums, behavior trees, services, scoring, both dispatchers | FastAPI, SQLModel, AS2 wire classes | `notes/architecture-hexagonal.md`, `test/architecture/` |
| `vultron/core/behaviors/` | py_trees trees and nodes; `BTBridge` execution under a module-level `RLock`; blackboard snapshot/restore (`blackboard_scope.py`) | `use_cases/` imports | `vultron/core/behaviors/bridge.py`, `test/architecture/test_behaviors_no_use_case_imports.py` |
| `vultron/core/predicates/` | Pure predicate functions (role checks, embargo eligibility, role-gated state invariants) — no I/O, no DataLayer | `behaviors/`, `services/`, `ports/` imports (cycle risk) | `notes/predicates-rule-layer.md` |
| `vultron/core/ports/` | Protocol contracts: `DataLayer`, `ActivityDispatcher`, `TriggerDispatcher`, `WireRenderPort`, `TriggerActivityPort`, `SyncActivityPort`, emitter and persistence ports | `BaseModel` types in port signatures | `vultron/core/ports/AGENTS.md` |
| `vultron/wire/as2/` | AS2 vocabulary (Pydantic), parser, unknown-key disposition, rehydration, semantic extractor, activity factories | Core logic beyond `core/models/` and `core/states/` imports; FastAPI | `vultron/wire/as2/AGENTS.md` |
| `vultron/semantic_registry/` | Ordered received-activity patterns and `use_case_map()` | Use-case logic | `vultron/semantic_registry/__init__.py` |
| `vultron/trigger_registry/` | One `TriggerEntry` per trigger verb (request model, use case, result type, exposure, spec IDs) | Per-verb behavior | `vultron/trigger_registry/__init__.py` |
| `vultron/adapters/driving/` | FastAPI routers, inbox orchestration, outbox handling and monitor, CLI; `shared_inbox.py` is a `NotImplementedError` stub | Business logic, persistence | `vultron/adapters/driving/fastapi/` |
| `vultron/adapters/driven/` | SQLite data layer (CRUD + queues), outbound HTTP delivery, sync adapter, trigger-activity adapter, wire render adapter | Core domain rules | `vultron/adapters/driven/datalayer_sqlite/`, `vultron/adapters/driven/wire_render/` |
| `vultron/adapters/connectors/` | Third-party tracker translations (Jira and VINCE examples) and a connector loader | Direct protocol handling | `vultron/adapters/connectors/` |
| `vultron/config/` | Settings models, YAML + env loading, `get_config()` | Adapter or core imports | `vultron/config/app.py`, `vultron/config/actor.py` |
| `vultron/bt/` | Legacy BT simulator (custom engine, read-only reference for protocol BTs) | Use by production code or demo scenarios | `notes/bt-composability.md`, `test/architecture/test_demo_no_bt_imports.py` |

### 4) Reused Patterns

| Pattern | Where found | Why it exists |
|---------|-------------|---------------|
| Port / Protocol | `vultron/core/ports/` | Decouple domain from adapter implementations; structural conformance without inheritance |
| Use-Case class (`UseCase` Protocol) | `vultron/core/ports/use_case.py`, `vultron/core/use_cases/` | Encapsulate one business operation; consistent `__init__(dl, request) + execute()` contract |
| Table-driven dispatch | `vultron/semantic_registry/` (`use_case_map()`), `vultron/trigger_registry/` (`TRIGGER_REGISTRY`) | Route inbound events and trigger verbs to use cases without per-handler decorators; the trigger table also feeds route-to-row and exposure ratchets |
| py_trees behavior trees behind `BTBridge` | `vultron/core/behaviors/` | Encode CVD sub-protocol logic as composable, testable trees; the bridge owns setup, blackboard scope and the global lock |
| Shared received-tree factory | `vultron/core/behaviors/case/receive_activity_tree.py` | One composition order (intake → guards → commit → effects) for every received tree (ADR-0111) |
| CASE_MANAGER gate | `create_case_manager_gated_tree` in `vultron/core/behaviors/case/nodes/role_gates.py`; `not_case_manager_refusal()` in `vultron/core/use_cases/received/_bt_verdict.py` | Effects owned by the CASE_MANAGER run only on that actor; another receiver reports `REFUSED`, never `SKIPPED` (BT-17-001, HP-01-005) |
| Factory function per object type | `vultron/wire/as2/factories/` | Construct outbound AS2 activities in one place |
| `pydantic-settings` layered config | `vultron/config/app.py` | Merge YAML file + env vars + defaults in a single `AppConfig` object |
| Typed ports on BT DataLayer nodes | `vultron/core/behaviors/` (`INPUT_PORTS`/`OUTPUT_PORTS`) | Declare blackboard key dependencies as typed class attributes instead of calling `register_key()` at runtime; enforced by `test/architecture/test_no_bare_register_key_datalayer_nodes.py` (BTND-03-009) |
| `WireRenderPort` driven port | `vultron/core/ports/wire_render.py` + `vultron/adapters/driven/wire_render/as2.py` | Lets core obtain wire-shaped (AS2 camelCase) JSON without importing `vultron/wire/`; the adapter returns the `CoreObject`'s own by-alias dump (ADR-0099) and refuses anything that is not a `CoreObject` |
| Sealed outbound body | `vultron/adapters/outbox_sealed_body.py` | The JSON a factory produced is the ledger snapshot and the delivered body, byte for byte (VM-08-003) |

### 5) Known Architectural Risks

- **Core-boundary ratchets fully passing**: `KNOWN_VIOLATIONS` is `frozenset()` in both `test_core_no_adapter_imports.py` and `test_core_no_wire_imports.py`.
- **Wire→core imports are governed by an allow-list, not a ratchet**: `test_wire_core_import_allowlist.py` enforces that wire MAY import `vultron/core/models/` and `vultron/core/states/`, and nothing else under `vultron/core/` (ARCH-22-001, ARCH-22-002 as amended by ADR-0099).
  The substantive rule is ARCH-01-003: no handler, case or journal logic in wire.
- **State machine coupling via the transitions library**: `vultron/core/states/` and `vultron/core/services/embargo_lifecycle/base.py` import `transitions` directly, so a third-party state machine library sits in core.
- **Process-global py_trees blackboard**: BT executions share `py_trees.blackboard.Blackboard.storage`.
  `BTBridge` serializes executions with a module-level `RLock`, and `blackboard_scope.py` snapshots and restores execution-scoped keys, but any key outside those managed sets can leak between trees.
- **Core modules over the CS-18 size cap**: several core files (for example `vultron/core/behaviors/helpers.py`, `vultron/core/use_cases/received/embargo.py`, `vultron/core/behaviors/bridge.py`) exceed the 500-line threshold of CS-18-001 (see `CONCERNS.md`).
- **Demo layer mixed into `vultron/demo/`**: demo code imports from adapters, which is appropriate, but the boundary between "demo" and "production use case" is not always clear.

### 6) Evidence

- `notes/architecture-hexagonal.md`
- `AGENTS.md`
- `vultron/core/AGENTS.md`
- `specs/architecture.yaml` (ARCH spec group)
- `vultron/adapters/driving/fastapi/main.py`
- `vultron/adapters/driving/fastapi/routers/actors/_routes.py`
- `vultron/adapters/driving/fastapi/inbox_orchestration.py`
- `vultron/adapters/driving/fastapi/trigger_runner.py`
- `vultron/core/dispatcher.py`
- `vultron/core/trigger_dispatcher.py`
- `vultron/core/ports/datalayer.py`
- `vultron/core/ports/use_case.py`
- `vultron/core/ports/wire_render.py`
- `vultron/core/behaviors/bridge.py`
- `vultron/core/behaviors/blackboard_scope.py`
- `vultron/core/behaviors/case/receive_activity_tree.py`
- `vultron/semantic_registry/__init__.py`
- `vultron/trigger_registry/__init__.py`
- `vultron/adapters/driven/wire_render/as2.py`
- `test/architecture/test_core_no_adapter_imports.py`
- `test/architecture/test_core_no_wire_imports.py`
- `test/architecture/test_wire_core_import_allowlist.py`
- `test/architecture/test_no_bare_register_key_datalayer_nodes.py`
- `test/architecture/test_no_dl_mutations_in_execute.py`
