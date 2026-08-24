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

### There is no shared DataLayer

ADR-0072 made per-actor storage the layout rather than a per-query filter. Every
`SqliteDataLayer` belongs to exactly one actor, `actor_id` is a required keyword,
and `actor_id=None` no longer constructs (DL-07-001, DL-07-002). One actor's
writes cannot change what another reads, including writes to the same object ID —
two actors may each hold their own replica of it.

Practically: each actor gets its own SQLite file, named by
`actor_slug(actor_id)`, and its inbox/outbox queues live in that file rather than
being keyed by an `actor_id` column. There is no unscoped or "admin" mode to fall
back to, so a node-wide view must fan out over stores explicitly —
`hosted_actor_ids()` enumerates them.

### Identity contract: canonical URI must match

The actor URI used to open a store must be the canonical URI — `actor.id_` — not
a short ID or a bare URL path segment (ARCH-13-003). The URI *selects the store*,
so a short id opens a different and empty one. Where a request carries a path
segment, resolve it with `canonical_actor_uri()` before opening anything; that is
what `get_canonical_actor_dl` does.

### Crossing to another actor's store

`clone_for_actor(actor_id)` is the only sanctioned route (DL-07-005), and
`vultron/core/behaviors/store_scope.py::store_for_actor` holds the guard logic
around it so the decision is not re-derived per call site. Pass
`require_same_authority=True` when the point of the write is to publish something
the named actor *serves*: `clone_for_actor` succeeds for any well-formed id, so
without the guard a remote actor's id silently opens a fresh empty local store.

### Retired: the `ActorScopedDataLayer` protocol (#655)

A dedicated protocol was planned for static enforcement of scope boundaries. It
is no longer needed and has been deleted: a DataLayer cannot exist unscoped, so
the boundary is enforced by construction. ARCH-13-001/002/004/005 were retired
with it; ARCH-13-003 survives, amended.
