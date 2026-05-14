# Architecture

## Core Sections (Required)

### 1) Architectural Style

- Primary style: layered hexagonal architecture with an explicit wire-format
  layer and event-driven background processing
- Why this classification: the repository guidance and sampled modules separate
  `core`, `wire`, and `adapters`, with `DataLayer` and dispatcher protocols in
  `core/ports/`, AS2 translation in `wire/`, and FastAPI/SQLite/HTTP delivery
  code in adapters.
- Primary constraints:
  1. Core code must remain isolated from FastAPI and adapter types.
  2. AS2-to-domain mapping is centralized in the semantic extraction path.
  3. HTTP processing uses background tasks and outbox draining instead of doing
     all work inline in the request handler.

### 2) System Flow

```text
HTTP request -> FastAPI app/router -> inbox handler + rehydration ->
semantic extraction -> dispatcher/use case -> DataLayer + outbox ->
OutboxMonitor -> outbox_handler ->
ASGIEmitter (co-located) | DeliveryQueueAdapter (remote) ->
peer inbox HTTP POST
```

Evidence-backed flow:

1. Docker and local API startup target
   `vultron.adapters.driving.fastapi.main:app`.
2. The root app mounts `app_v2` at `/api/v2`.
3. Actor inbox handling rehydrates AS2 activities and extracts a domain event.
4. The dispatcher looks up the use-case class from the semantic registry map.
5. Use cases persist/read state through the `DataLayer` port and adapter.
6. Outbox processing is drained by a background monitor and delivered over HTTP.

### 3) Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|-----------------|------|--------------|----------|
| `vultron/core/` | Domain events, ports, dispatcher, use cases | FastAPI and adapter details | `AGENTS.md`, `vultron/core/ports/datalayer.py`, `vultron/core/dispatcher.py` |
| `vultron/wire/as2/` | AS2 vocabulary, pattern matching, semantic extraction | Case lifecycle behavior | `vultron/wire/as2/extractor.py` |
| `vultron/adapters/driving/fastapi/` | HTTP routing, dependency injection, background task scheduling | Persistent model ownership | `vultron/adapters/driving/fastapi/app.py`, `vultron/adapters/driving/fastapi/deps.py` |
| `vultron/adapters/driven/` | SQLite persistence and outbound HTTP delivery | FastAPI request translation | `vultron/adapters/driven/datalayer_sqlite.py`, `vultron/adapters/driven/delivery_queue.py` |
| `vultron/demo/` | Operator/demo CLI workflows and seeding | Authoritative storage API | `vultron/demo/cli.py`, `vultron/demo/utils.py` |

### 4) Reused Patterns

| Pattern | Where found | Why it exists |
|---------|-------------|---------------|
| Port/adapter split | `vultron/core/ports/datalayer.py`, `vultron/adapters/driven/datalayer.py` | Keep core independent of storage implementation |
| Dispatcher + routing table | `vultron/core/dispatcher.py`, `vultron/semantic_registry.py` | Route semantic events to use cases without router-specific logic |
| Dependency injection | `vultron/adapters/driving/fastapi/deps.py` | Centralize shared/shared-scoped DataLayer and TriggerService seams |
| Background worker loop | `vultron/adapters/driving/fastapi/outbox_monitor.py` (polls; calls `outbox_handler.py`) | Drain outboxes asynchronously for all actors |
| ASGI-first delivery | `vultron/adapters/driven/asgi_emitter.py`, `vultron/adapters/driving/fastapi/app.py` | Deliver to co-located actors in-process via ASGI; fall back to HTTP for remote actors |
| Behavior trees | `docs/adr/0002-model-processes-with-behavior-trees.md`, `AGENTS.md` | Model multi-state CVD workflows and automation paths |

### 5) Known Architectural Risks

- Process-local singleton/stateful wiring: the module-level dispatcher and
  process-local DataLayer façade make startup order and process model important.
- Shared-vs-actor-scoped DataLayer behavior is subtle and requires canonical
  actor-ID normalization to keep inbox/outbox operations consistent.

### 6) Evidence

- `AGENTS.md`
- `notes/architecture-ports-and-adapters.md`
- `vultron/adapters/driving/fastapi/main.py`
- `vultron/adapters/driving/fastapi/app.py`
- `vultron/adapters/driving/fastapi/inbox_handler.py`
- `vultron/core/dispatcher.py`
- `vultron/semantic_registry.py`
- `vultron/adapters/driving/fastapi/outbox_monitor.py`
- `vultron/adapters/driving/fastapi/outbox_handler.py`
- `vultron/adapters/driven/asgi_emitter.py`
- `vultron/core/ports/emitter.py`
