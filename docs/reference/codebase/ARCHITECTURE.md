# Architecture

## Core Sections (Required)

### 1) Architectural Style

- Primary style: layered hexagonal architecture with an explicit wire-format
  layer and asynchronous delivery/background processing
- Why this classification: the repository separates `core`, `wire/as2`, and
  `adapters`; core owns ports and use cases, wire owns ActivityStreams parsing
  and semantic extraction, and adapters own HTTP, storage, and delivery wiring.
- Primary constraints:
  1. Core code should not depend on FastAPI/framework details.
  2. AS2-to-domain translation is centralized in the extractor/semantic-registry
     path.
  3. Inbox/outbox work is deferred to background tasks and the outbox monitor.

### 2) System Flow

```text
HTTP request -> FastAPI router -> background inbox pipeline ->
wire rehydration + semantic matching -> dispatcher -> use case ->
DataLayer save/read + outbox enqueue -> OutboxMonitor -> ActivityEmitter ->
co-located ASGI delivery or remote HTTP inbox POST
```

Evidence-backed flow:

1. Docker and local startup use `vultron.adapters.driving.fastapi.main:app`.
2. `main.py` mounts `app_v2` and configures logging, dispatcher, and emitter.
3. Inbox routes accept requests and schedule background work instead of doing
   full processing inline.
4. Semantic matching is driven by `SEMANTIC_REGISTRY`; event extraction happens
   in `vultron.wire.as2.extractor._extract.extract_intent()`.
5. The dispatcher looks up a use-case class by `MessageSemantics` and runs it
   with a `DataLayer` plus injected ports.
6. Use cases persist/read via the `DataLayer` port and queue outbound work.
7. `OutboxMonitor` drains actor outboxes and hands delivery to `ASGIEmitter`
   (local) or `DemoHttpDeliveryAdapter` (remote fallback).

### 3) Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|-----------------|------|--------------|----------|
| `vultron/core/` | Domain models, ports, dispatcher, use cases | FastAPI routing and direct transport details | `notes/architecture-hexagonal.md`, `vultron/core/ports/datalayer.py`, `vultron/core/dispatcher.py` |
| `vultron/wire/as2/` | AS2 vocabulary, pattern instances, rehydration, event extraction | Case lifecycle rules and HTTP concerns | `vultron/wire/as2/extractor/__init__.py`, `vultron/wire/as2/extractor/_extract.py` |
| `vultron/semantic_registry/` | Ordered mapping from semantics to patterns, events, and use cases | Raw HTTP handling | `vultron/semantic_registry/__init__.py`, `vultron/semantic_registry/report.py` |
| `vultron/adapters/driving/fastapi/` | HTTP endpoints, dependency injection, background task scheduling | Domain persistence policy | `vultron/adapters/driving/fastapi/app.py`, `vultron/adapters/driving/fastapi/routers/actors/_routes.py` |
| `vultron/adapters/driven/` | SQLite persistence, emitters, sync/trigger adapters | Request routing | `vultron/adapters/driven/datalayer_sqlite/__init__.py`, `vultron/adapters/driven/asgi_emitter.py`, `vultron/adapters/driven/sync_activity_adapter.py`, `vultron/adapters/driven/trigger_activity_adapter/__init__.py` |
| `vultron/demo/` | Operator/demo CLI flows and verification | Canonical business interfaces | `vultron/demo/README.md`, `vultron/demo/cli.py` |

### 4) Reused Patterns

| Pattern | Where found | Why it exists |
|---------|-------------|---------------|
| Port/adapter split | `vultron/core/ports/`, `vultron/adapters/driven/`, `vultron/adapters/driving/` | Keep domain logic isolated from storage and transport details |
| Ordered semantic registry | `vultron/semantic_registry/__init__.py` | Route inbound AS2 activities by first-match semantics |
| App factory isolation | `vultron/adapters/driving/fastapi/app.py:create_app` | Give tests/co-located apps isolated dispatcher and DataLayer state |
| Background task handoff | `vultron/adapters/driving/fastapi/routers/actors/_routes.py` | Return HTTP 202 quickly while processing inbox work asynchronously |
| Background outbox monitor | `vultron/adapters/driving/fastapi/outbox_monitor.py` | Drain actor outboxes outside request handlers |
| Local-first delivery fallback | `vultron/adapters/driven/asgi_emitter.py` | Use in-process ASGI for co-located actors and HTTP fallback for remote ones |
| Domain→wire translation adapters | `vultron/adapters/driven/sync_activity_adapter.py`, `vultron/adapters/driven/trigger_activity_adapter/__init__.py` | Keep wire factory imports out of `core/` |

### 5) Known Architectural Risks

- The mounted production-style path still configures module-level defaults for
  the emitter and shared DataLayer cache, so global state remains a risk even
  though `create_app()` isolates test/co-located instances.
- Actor-scoped versus shared `DataLayer` usage is subtle; queue operations rely
  on canonical actor IDs and scoped clones.
- Remote signed delivery and shared-inbox handling are still stubbed, so the
  current delivery architecture is prototype-only for remote interoperability.

### 6) Evidence

- `notes/architecture-hexagonal.md`
- `vultron/adapters/driving/fastapi/main.py`
- `vultron/adapters/driving/fastapi/app.py`
- `vultron/adapters/driving/fastapi/routers/actors/_routes.py`
- `vultron/core/dispatcher.py`
- `vultron/core/ports/datalayer.py`
- `vultron/semantic_registry/__init__.py`
- `vultron/wire/as2/extractor/_extract.py`
- `vultron/adapters/driven/asgi_emitter.py`
- `vultron/adapters/driving/fastapi/outbox_monitor.py`
