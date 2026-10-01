# Core Ports — Design Rules

> Full DataLayer architecture analysis, CasePersistence narrowing rationale,
> auto-rehydration contract, and vocabulary registry entanglement:
> [`notes/datalayer-design.md`](../../../../notes/datalayer-design.md)

Core ports are split by direction.

**Inbound ports (driving)** — external adapters call into core:

- `UseCase` Protocol (`core/ports/use_case.py`) — primary inbound port.
- `ActivityDispatcher` Protocol (`core/ports/dispatcher.py`) — received-side
  routing entry: `dispatch(event, dl) -> HandlerResult`, routed by
  `SEMANTIC_REGISTRY`.
- `TriggerDispatcher` Protocol (`core/ports/trigger_dispatcher.py`) —
  trigger-side routing entry: one `trigger(request, dl) -> ResultT_co` method,
  routed by `vultron/trigger_registry/` (ADR-0110). The return type is bound
  to the request's type, so a router gets the verb's `TriggerResult` subtype
  with no cast and no per-verb method (UCORG-05-006). Implementation:
  `core/trigger_dispatcher.py` (`RegistryTriggerDispatcher`). It is the only
  trigger driving port: `test/architecture/test_trigger_port_single_method.py`
  fails on a second public method or a per-verb facade under `vultron/core/`.

**Outbound ports (driven)** — core calls outward:

- `DataLayer` (`core/ports/datalayer.py`) — persistence contract.
- `CasePersistence` / `CaseOutboxPersistence` — narrower persistence
  ports.
- `ActivityEmitter` (`core/ports/emitter.py`) — outbound delivery of an
  activity's *sealed body* (JSON text), relayed unchanged (VM-08-003).

Naming principle: choose domain intent, not transport implementation.

## Dispatch vs Emit Terminology

Use these terms consistently:

- **Dispatch** (inbound): driving adapter -> dispatcher/use case in core.
- **Emit** (outbound): core action -> adapter delivery to recipients.

One emitter adapter is used for all inter-actor delivery (ADR-0042):

- `HttpDeliveryAdapter` — HTTP POST to `{actor_uri}/inbox/`; treats every
  recipient as remote (OX-12-001).

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
- Do not expose wire-layer (`as_*`) or adapter-layer models as cross-layer API
  shape. A core-owned domain model (`VultronEvent`, `TriggerRequest`,
  `UseCaseResult`) **is** an explicit domain type and is the right boundary
  type, even though it is a Pydantic `BaseModel` — the accepted
  `ActivityDispatcher.dispatch(event, dl)` port is the precedent
  (ADR-0009, ADR-0110). Reading this rule as "no `BaseModel` anywhere" is what
  produced a 27-method port that flattened typed requests into `Any` scalars.
- **A driving port is O(1) in the behaviors behind it.** Routing from a
  discriminator (semantics, trigger verb) to a use case is data in a registry,
  not a method per verb. A port whose method count grows with the use-case
  count hides nothing and is a duplicated declaration, not an abstraction.
- **Never `Mock(spec=<driving port>)`.** A driving port is a seam for the code
  *in front of* it (routers, CLI). Tests of that code run the real dispatcher
  over a real in-memory store; tests of use cases construct them directly.
  A mock of the driving port asserts only that a method was called, which is
  the one thing the port's callers do not need verified.
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
