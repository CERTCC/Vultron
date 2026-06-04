# Core Ports — Design Rules

> Full DataLayer architecture analysis, CasePersistence narrowing rationale,
> auto-rehydration contract, and vocabulary registry entanglement:
> [`notes/datalayer-design.md`](../../../../notes/datalayer-design.md)

Core ports are split by direction.

**Inbound ports (driving)** — external adapters call into core:

- `UseCase` Protocol (`core/ports/use_case.py`) — primary inbound port.
- `ActivityDispatcher` Protocol (`core/ports/dispatcher.py`) — routing
  entry.

**Outbound ports (driven)** — core calls outward:

- `DataLayer` (`core/ports/datalayer.py`) — persistence contract.
- `CasePersistence` / `CaseOutboxPersistence` — narrower persistence
  ports.
- `ActivityEmitter` (`core/ports/emitter.py`) — outbound activity
  delivery.

Naming principle: choose domain intent, not transport implementation.

## Dispatch vs Emit Terminology

Use these terms consistently:

- **Dispatch** (inbound): driving adapter -> dispatcher/use case in core.
- **Emit** (outbound): core action -> adapter delivery to recipients.

Two emitter adapters are currently used:

- `DeliveryQueueAdapter` (remote HTTP delivery path).
- `ASGIEmitter` (co-located ASGI delivery, HTTP fallback when non-local).

## Use Cases as Incoming Ports

Use-case callables represent the domain's incoming ports. Driving
adapters should be able to invoke them without direct coupling to AS2 or
HTTP objects.

## Named Ports

### `SyncActivityPort`

`SyncActivityPort` is the driven port for sync-oriented outbound
activities. It handles domain-to-wire conversion and outbox persistence in
the adapter implementation (`SyncActivityAdapter`) while keeping core free
of wire imports.

### `TriggerActivityPort`

`TriggerActivityPort` is the driven port for trigger-originated outbound
activities. The adapter implementation (`TriggerActivityAdapter`) is the
sole translation point for trigger-side domain->wire construction.

### Server-Level Inbox: Deferred Design Decision

A server-level inbox is recognized as a future option, but current
behavior is direct delivery service -> actor inbox. Actor-level
validation is preferred at prototype stage over a pre-validation
buffering layer.

## Port Interface Hygiene

- Port and adapter signatures should use explicit domain types.
- Do not expose `pydantic.BaseModel` directly as cross-layer API shape.
- Keep port contracts minimal, typed, and semantically named.

## DataLayer Operating Rules

- Persist with `dl.save(obj)` — NEVER call `object_to_record()` + `dl.update()`
- `dl.read(id)` MUST return a fully typed, rehydrated domain object (never a
  raw dict). If it returns something that needs `model_validate()`, that is a
  DataLayer adapter bug.
- Do NOT call `get()` or `by_type()` in new core code — use `read()` and
  `list_objects()` instead. Those are deprecated compatibility shims.
- See `notes/datalayer-design.md` for the full design rationale and migration
  direction.
