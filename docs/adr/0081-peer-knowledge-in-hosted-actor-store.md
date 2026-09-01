---
status: accepted
date: 2026-08-31
deciders: Allen D. Householder
consulted: Claude Sonnet 4.6
informed: []
---

# Peer Knowledge Lives in the Hosted Actor's Own Store, Not as a Hosted Actor

## Context and Problem Statement

`POST /actors/` minted a local store and actor record for every id it received,
including ids that belonged to actors on remote nodes.  Because `actor_slug()`
strips scheme and authority, two ids with the same final path segment but
different authorities (e.g. `http://finder:7999/.../alice` and
`http://vendor:7999/.../alice`) mapped to the same SQLite file.  The collision
was logged as a warning and the second write silently returned the first actor's
record, so `hosted_actor_ids()` reported remote actors as locally hosted and
subsequent delivery attempts failed in surprising ways.

Issue #2549 identified the root cause as two separate confusions:

1. **Route confusion** — `POST /actors/` should only create actors whose
   authority matches the serving node's `base_url`.  Foreign-authority ids
   describe actors that live elsewhere; registering them as hosted actors is
   wrong.

2. **Concept confusion** — the mechanism that nodes use to know about remote
   peers (address-book entries) was not distinguished from the mechanism that
   makes an actor hosted on this node (a store + actor record).  The only reason
   to call `POST /actors/` with a foreign id was to get an address-book entry,
   but the route created a phantom store instead.

## Decision

**Foreign-authority ids are rejected at `POST /actors/`.**

An `actor_id` whose scheme and authority do not match the serving node's
configured `base_url` returns `422 Unprocessable Content`.  The check is at the
route layer; `canonical_actor_uri()` and `actor_slug()` are not changed.

**Peer knowledge is stored as a `CoreActor` record in the *host* actor's own store
via a new `POST /actors/{actor_id}/peers/` endpoint.**

The new endpoint:

- Validates that `actor_id` (the path parameter) names an actor hosted on this
  node (returns 404 otherwise).
- Accepts `{ "id": "<peer_uri>", "name": "...", "actor_type": "..." }`.
- Writes a `CoreActor` record into the host actor's DataLayer (not as a
  separately hosted actor).
- Is idempotent: a second call with the same peer id returns 200 with the
  existing record.

The peer record lives in the host actor's store.  It cannot be read by other
actors (ADR-0073); it is an address-book entry, not a claim that this node
hosts the peer.

## Consequences

### Positive

- `hosted_actor_ids()` only reports actors that are genuinely hosted on this
  node.
- The store-collision path in `get_actor_engine` becomes unreachable for
  correctly behaved production callers; the guard logs a WARNING and remains
  permissive so the test harness (which legitimately runs multiple nodes in
  one process) continues to function.
- Demo seeding helpers (`seed_containers*`) now use `seed_peer(...)` for Phase 2
  cross-container registrations.

### Negative

- Callers that previously called `POST /actors/` with a foreign id to register
  a peer must be updated to call `POST /actors/{id}/peers/` instead.  The demo
  CLI and all `seed_containers*` helpers have been updated; external clients
  may need updating.

### Neutral

- `canonical_actor_uri()` is unchanged.  It still returns foreign-authority ids
  verbatim, which is correct for outbound delivery addressing.
- `actor_slug()` is unchanged.  Its authority-stripping behavior is now only
  reachable for local actors, so cross-authority collisions are unreachable in
  practice.

## References

- Issue #2549 — root-cause analysis and reproduction steps
- ADR-0073 — per-actor store isolation (each actor gets its own SQLite file)
