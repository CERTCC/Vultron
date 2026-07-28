---
title: Adapter Patterns and Boundary Invariants
status: active
description: >
  Adapter category details, outbound activity construction via driven ports,
  DataLayer scope boundaries, and the uniform-HTTP inter-actor delivery model
  (ADR-0042).
related_notes:
  - notes/architecture-hexagonal.md
  - vultron/core/ports/AGENTS.md
  - vultron/adapters/driven/AGENTS.md
relevant_packages:
  - vultron/adapters
  - vultron/adapters/driven
  - vultron/adapters/driving
---

# Adapter Patterns and Boundary Invariants

## Adapter Categories in Practice

- **Driving adapters**: receive external input and trigger core logic.
- **Driven adapters**: implement outbound dependencies called by core.
- **Connectors**: boundary translators for third-party trackers/systems.

If a feature requires both directions, keep separate modules in
`adapters/driving/` and `adapters/driven/`.

---

## Outbound Delivery Invariants

1. Core emits domain events, not wire objects.
2. Event<->activity mapping is deterministic and non-enriching.
3. Recipients are domain-derived, not infra-injected.
4. Emission, transport delivery, and recipient acceptance are distinct stages.
5. Transport validation and semantic validation happen at different boundaries.

---

## Delivery Transport: Uniform HTTP (ADR-0042)

All inter-actor activity delivery goes over the REST inbox/outbox HTTP API
(HTTP POST to `{actor}/inbox/`). **Actors are treated as if every recipient
were remote** — there is no in-process shortcut for co-located actors. This
keeps co-located and remote delivery on one code path, so demos faithfully
model autonomous peers and inter-actor delivery bugs surface in-process
instead of being masked (concern #1723, ADR-0042, `outbox.yaml` OX-12).

- The production default `ActivityEmitter` is the HTTP delivery adapter.
- CaseActor canonical-ledger self-delivery (the `cc:`-to-self copy that loops
  a ledger-authoring entry back to its own inbox, CLP-10-001) is delivered
  over **HTTP loopback**, using the same path as any other recipient.
- **Application code MUST NOT construct `httpx.ASGITransport` directly**
  (OX-12-003). The only permitted use is FastAPI's `TestClient`, which uses
  `ASGITransport` internally to drive a single app's own endpoints.

> **Historical note:** a previous `ASGIEmitter` adapter delivered to
> co-located actors in-process (scheme+netloc match → direct ASGI call, with
> mount-prefix stripping and a reentrancy guard). It was the production
> default until ADR-0042 retired it. `architecture.yaml` ARCH-17 is
> superseded. Do not reintroduce an in-process delivery shortcut.

---

## Driven Ports for Outbound Activity Construction

Core must not construct wire-layer types directly. Outbound activity creation is
owned by driven ports in `core/ports/` and adapter implementations in
`adapters/driven/`.

### Baton-pass pattern

Core passes domain data at the port boundary. Adapter owns:

1. Domain -> wire conversion,
2. persistence of activity object,
3. outbox enqueueing,
4. returned activity identifiers/response payloads.

### Long-term BT-based flows

Expected end-state:

1. Received use cases hand events to behavior trees.
2. BT nodes make branching decisions.
3. BT leaves call driven ports for outbound actions.

### Remaining ARCH-01-001 violations

Some core->wire imports remain and require additional driven-port extraction.
Track ongoing violations in the associated ARCH-01-001 issue and spec links.

### Future delivery stubs

Architectural placeholders exist (tracked in GitHub issue #650):

- `adapters/driven/prod_http_delivery.py` — future signed remote HTTP delivery
  (`specs/outbox.yaml` OX-10-001–OX-10-004). **Must raise `NotImplementedError`
  if instantiated until implemented** (OX-10-004).
- `adapters/driving/shared_inbox.py` — future ActivityPub shared-inbox fan-out
  (`specs/outbox.yaml` OX-11-001–OX-11-004). **Must raise `NotImplementedError`
  if instantiated until implemented** (OX-11-004).

Both stubs are transport-only concerns. The core layer must not reference them
directly; they are driven/driving adapter responsibilities only.

### Architecture boundary ratchet test

`test/architecture/test_core_no_adapter_imports.py` enforces core->adapters
boundary with a ratchet (`KNOWN_VIOLATIONS`) so new violations fail immediately.

---

## DataLayer Scope Boundaries

### Shared vs actor-scoped DataLayer

`SqliteDataLayer(actor_id=None)` provides shared/global domain storage view.
`SqliteDataLayer(actor_id=<canonical actor URI>)` is required for inbox/outbox
queue operations.

Queue methods key off `self._actor_id`; using shared mode for queues writes to a
phantom key and hides actor queues.

### Identity contract: canonical URI must match

The actor URI used for queue write paths and actor-scoped read paths must match
exactly (string-equal). Normalize to canonical actor IDs before constructing
actor-scoped DataLayers.

### Future: `ActorScopedDataLayer` protocol (tracked in #655)

A dedicated protocol is planned for static enforcement of scope boundaries.
Until then, tests enforce the contract behavior.
