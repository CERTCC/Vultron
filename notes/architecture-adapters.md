---
title: Adapter Patterns and Boundary Invariants
status: active
kind: guidance
description: >
  Outbound activity construction via driven ports, stub and naming rules,
  DataLayer scope boundaries, and the uniform-HTTP inter-actor delivery model
  (ADR-0042). Adapter categories live in notes/architecture-hexagonal.md.
related_specs:
  - specs/outbox.yaml
related_notes:
  - notes/architecture-hexagonal.md
  - notes/outbox.md
  - vultron/core/ports/AGENTS.md
  - vultron/adapters/driven/AGENTS.md
relevant_packages:
  - vultron/adapters
  - vultron/adapters/driven
  - vultron/adapters/driving
---

# Adapter Patterns and Boundary Invariants

Adapter categories (driving, driven, connector, wire) and the rule against
mixing directions in one module: `notes/architecture-hexagonal.md` § "Adapter
Categories".

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
instead of being masked (ADR-0042, `outbox.yaml` OX-12).

- The production default `ActivityEmitter` is the HTTP delivery adapter.
- An activity whose recipient is the sender's own inbox (a participant-role
  activity addressed to a CASE_MANAGER that is the same actor, CLP-10-001) is
  delivered over **HTTP loopback**, using the same path as any other recipient.
  The CASE_MANAGER never mails itself a `cc:` copy of its own emission: the
  emitting tree commits the ledger entry (ADR-0109).
- **Application code MUST NOT construct `httpx.ASGITransport` directly**
  (OX-12-003). The only permitted use is FastAPI's `TestClient`, which uses
  `ASGITransport` internally to drive a single app's own endpoints.
- Do not reintroduce an in-process delivery shortcut for co-located actors;
  ADR-0042 removed it.

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

### BT-based flows

Received use cases hand events to behavior trees, BT nodes make the branching
decisions, and BT leaves call driven ports for outbound actions.

### Stub adapters raise `NotImplementedError`

**Any stub adapter raises `NotImplementedError` when instantiated** (OX-10-004,
OX-11-004). A docstring-only placeholder imports and constructs cleanly, so a
caller wired to it fails silently instead of at startup. The current stubs are
`adapters/driven/prod_http_delivery.py` (signed remote HTTP delivery, OX-10) and
`adapters/driving/shared_inbox.py` (ActivityPub shared-inbox fan-out, OX-11).
Both are transport-only; core never references them.

### Transport-role naming stays explicit

Delivery adapter module and class names state their transport role:
`http_delivery.py` / `HttpDeliveryAdapter` is the sole delivery path (ADR-0042),
and `prod_http_delivery.py` / `ProdHttpDeliveryAdapter` is the signed-remote stub.
`demo_http_delivery.py` is a deprecated re-export shim; import from
`http_delivery` instead. A rename of a transport-role adapter changes
the core ports docs, adapter notes, ADR references and
`docs/reference/codebase/` pages in the same change.

### Architecture boundary ratchet test

`test/architecture/test_core_no_adapter_imports.py` enforces core->adapters
boundary with a ratchet (`KNOWN_VIOLATIONS`) so new violations fail immediately.

---

## DataLayer Scope Boundaries

### There is no shared DataLayer

Per-actor storage is the layout, not a per-query filter (ADR-0073). Every
`SqliteDataLayer` belongs to exactly one actor and `actor_id` is a required
keyword (DL-07-002). One actor's writes cannot change what another reads,
including writes to the same object ID — two actors may each hold their own
replica of it (DL-07-001).

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
what `get_actor_dl` does (and `get_trigger_dl`, the trigger routes' override
seam, delegates to it).

### Crossing to another actor's store

`clone_for_actor(actor_id)` is the only sanctioned route (DL-07-005), and
`vultron/core/behaviors/store_scope.py::store_for_actor` holds the guard logic
around it so the decision is not re-derived per call site. Pass
`require_same_authority=True` when the point of the write is to publish something
the named actor *serves*: `clone_for_actor` succeeds for any well-formed id, so
without the guard a remote actor's id silently opens a fresh empty local store.

No separate scope-enforcing protocol is needed: a DataLayer cannot exist
unscoped, so the boundary holds by construction.
