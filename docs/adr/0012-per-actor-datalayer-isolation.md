---
status: accepted
date: 2026-03-19
deciders: ahouseholder
consulted: notes/domain-model-separation.md, notes/architecture-ports-and-adapters.md
informed: plan/IMPLEMENTATION_PLAN.md
---

# Per-Actor DataLayer Isolation

## Context and Problem Statement

All actors currently share a singleton `TinyDbDataLayer` backed by a single
`plan/mydb.json` file. This violates `specs/case-management.md` CM-01-001
(actor isolation): Actor A can read and mutate Actor B's records.

PRIORITY 100 requires each actor to have an isolated data store so that
actors can only interact through the Vultron Protocol (ActivityStreams
messages), not through shared state.

Three related design decisions must be made before implementation can begin:

1. **DataLayer isolation strategy** — how to partition data per actor.
2. **`get_datalayer` FastAPI DI strategy** — how to inject a per-actor
   DataLayer into route handlers given the current zero-argument singleton
   factory pattern.
3. **`actor_io.py` inbox/outbox ownership** — whether the in-memory
   inbox/outbox store in `vultron/api/v2/data/actor_io.py` should migrate
   into the per-actor DataLayer or remain as a separate adapter.
4. **OUTBOX-1 scope boundary** — whether outbound delivery is in scope for
   PRIORITY 100 or deferred.

## Decision Drivers

- Actors must not be able to read or mutate each other's state (CM-01-001).
- The `DataLayer` port/adapter separation must be preserved; core must not
  depend on the backing store.
- The DI pattern must be consistent across all 20+ route files and trigger
  endpoints; the chosen pattern must be simple to apply uniformly.
- `actor_io.py` predates the DataLayer abstraction and is not per-actor
  isolated; its role must be resolved to avoid creating a parallel state
  management path.
- The prototype must continue to work with the existing Docker Compose
  setup; a one-step migration to a robust production backing store is
  desirable.

## Considered Options

### DataLayer isolation strategy

- **Option A** — One TinyDB file per actor (e.g., `{actor_id}.json`)
- **Option B** — Namespace prefix per actor in one TinyDB file (one table
  per actor)
- **Option C** — In-memory DataLayer per actor (no persistence)
- **Option D** — MongoDB Community Edition per actor in Docker

### `get_datalayer` FastAPI DI strategy

- **DI-1** — Closure lambda: `Depends(lambda actor_id: get_datalayer(actor_id))`
- **DI-2** — Custom dependency class (`class GetDataLayer: def __call__(...)`)
- **DI-3** — Explicit parameter threading (pass `actor_id` everywhere)

### `actor_io.py` inbox/outbox ownership

- **IO-A** — Migrate inbox/outbox into per-actor DataLayer (TinyDB
  collections `{actor_id}_inbox` / `{actor_id}_outbox`)
- **IO-B** — Formalize `actor_io.py` as a named in-process queue adapter
  wired to the `ActivityEmitter` port, kept separate from DataLayer

### OUTBOX-1 scope boundary

- **OX-A** — Include local outbound delivery (OX-1.1–OX-1.4) as part of
  PRIORITY 100
- **OX-B** — Defer OUTBOX-1 until per-actor DataLayer isolation is proved
  out; merge as a follow-on task after ACT-3

## Decision Outcome

**DataLayer isolation: Option B — TinyDB namespace prefix**, with a
**concurrent MongoDB Community Edition** implementation as the
production-grade backing store.

Option B mirrors the natural collection-per-actor pattern of MongoDB and
requires only a modified `_table()` helper in `TinyDbDataLayer`. It keeps
a single backing file, supports the multi-tenant and vendor scenarios
described in `notes/domain-model-separation.md`, and makes the eventual
TinyDB → MongoDB migration straightforward because both use the same logical
namespace model.

Option A creates many files and complicates the DataLayer reset endpoint
used by demo scripts. Option C has no persistence and cannot be used for
Docker demos. A pure MongoDB-first approach (Option D alone) is the right
production target, but implementing it as the sole P100 step adds Docker
infrastructure risk on the critical path.

**`get_datalayer` DI strategy: DI-1 — closure lambda.**

`Depends(lambda actor_id=Path(...): get_datalayer(actor_id))` is the
simplest pattern, requires no new classes, and is consistent with FastAPI
conventions. It supports future dynamic actor instantiation without
architectural change. DI-2 adds unnecessary ceremony; DI-3 is too invasive
across 20+ route files.

**`actor_io.py` inbox/outbox ownership: IO-A — migrate into per-actor DataLayer.**

Inbox and outbox activities are persistent state. Storing them as TinyDB
collections (`{actor_id}_inbox`, `{actor_id}_outbox`) alongside other
per-actor records is architecturally consistent and avoids a parallel,
in-memory-only state management path. Once the per-actor DataLayer is in
place, `actor_io.py` can be removed (VCR-014).

`actor_io.py` is in `vultron/api/v2/data/`, predates the DataLayer
abstraction, and does not persist to disk — all three are violations of
the hexagonal architecture. IO-B formalizes the violation; IO-A removes it.

**OUTBOX-1 scope: OX-B — defer outbound delivery until ACT-3 is complete.**

The `ActivityEmitter` port stub (OX-1.0) and `DeliveryQueueAdapter` stub
are already in place. Local delivery (OX-1.1–OX-1.4) requires the per-actor
DataLayer inbox collection to exist (IO-A decision above), so OX-1.1 MUST
follow ACT-2. Deferring OUTBOX-1 until after ACT-3 keeps each task's scope
clear and avoids implementing delivery against a still-changing DataLayer.

### Consequences

- Good, because per-actor TinyDB tables enforce data isolation with minimal
  code change — only `TinyDbDataLayer.__init__` and `_table()` need updating.
- Good, because the closure lambda DI pattern is consistent, easy to audit,
  and can be applied uniformly across all route files in one pass (ACT-3).
- Good, because migrating inbox/outbox into DataLayer eliminates `actor_io.py`
  and the ACTOR_IO_STORE global (VCR-014 becomes unblocked after ACT-2).
- Good, because deferring OX-1.1 avoids delivery-against-a-moving-target risk.
- Neutral, because Option B (namespace prefix) is a prototype-grade solution;
  the MongoDB backend is the production target and should be implemented as
  part of the PRIORITY 100 / PRIORITY 300 transition.
- Bad, because every route file must be updated to pass `actor_id` to
  `get_datalayer` (ACT-3 scope); this is a large but mechanical change.

## Validation

- `uv run pytest --tb=short` passes after each of ACT-2 and ACT-3.
- Actor A's `dl.list()` does not return records belonging to Actor B.
- `actor_io.py` is removed after ACT-2 (VCR-014 acceptance criterion met).
- All inbox/outbox entries written via `actor_io` are now retrievable via
  the DataLayer inbox/outbox collections.

## Pros and Cons of the Options

### Option A — One TinyDB file per actor

- Good, because data isolation is trivially complete (separate files).
- Bad, because it creates many files and complicates DataLayer reset.
- Bad, because it diverges from the MongoDB collection model, making
  migration harder.

### Option B — Namespace prefix per actor (one TinyDB file)

- Good, because it mirrors MongoDB's collection-per-actor model.
- Good, because a single backing file is easier to manage in Docker demos.
- Good, because only `_table()` in `TinyDbDataLayer` needs updating.
- Neutral, because it is a prototype-grade isolation (not cryptographic
  separation), but sufficient for the research prototype purpose.

### Option C — In-memory DataLayer per actor

- Good, because isolation is trivially complete in tests.
- Bad, because it has no persistence; state is lost on restart.
- Bad, because Docker demos cannot use it.

### Option D — MongoDB Community Edition only

- Good, because it is the production-grade solution.
- Good, because each actor container can have its own MongoDB instance.
- Bad, because it adds Docker infrastructure complexity on the critical path.
- Neutral, because it is the intended production target; implementing
  Option B first provides a bridge with low risk.

### DI-1 — Closure lambda

- Good, because it is idiomatic FastAPI and requires no new classes.
- Good, because it expresses the actor-scoped intent inline at the dependency
  declaration site.
- Neutral, because the lambda syntax is slightly less readable than a class.

### DI-2 — Custom dependency class

- Good, because it is explicit.
- Bad, because it adds boilerplate for a trivial transformation.

### DI-3 — Explicit parameter threading

- Bad, because it requires invasive changes across all 20+ route files and
  every function in the call chain.

### IO-A — Migrate inbox/outbox into DataLayer

- Good, because it eliminates a parallel state management path.
- Good, because inbox/outbox activities persist across restarts.
- Good, because it unblocks VCR-014 (remove `actor_io.py`).
- Neutral, because it requires adding `{actor_id}_inbox` and
  `{actor_id}_outbox` collections to the DataLayer port interface or
  using a naming convention on existing collection methods.

### IO-B — Formalize actor_io.py as a queue adapter

- Good, because it separates in-flight queue semantics from persistent store.
- Bad, because it keeps a global in-memory store that violates actor isolation.
- Bad, because it creates two state management systems for actor data.

### OX-A — OUTBOX-1 in scope for PRIORITY 100

- Good, because it delivers end-to-end message flow in one phase.
- Bad, because OX-1.1 depends on the inbox DataLayer collection from IO-A,
  which is created in ACT-2; sequencing risk is high if ACT-2 is still in flux.

### OX-B — Defer OUTBOX-1 until after ACT-3

- Good, because ACT-2/ACT-3 scope stays clearly bounded.
- Good, because OX-1.1 can be implemented against a stable, tested DataLayer.
- Neutral, because end-to-end message flow is delayed by one phase.

## More Information

- `notes/domain-model-separation.md` — "Per-Actor DataLayer Isolation Options"
  and "Production Path: MongoDB Community Edition" sections.
- `notes/architecture-ports-and-adapters.md` — "Dispatch vs Emit Terminology"
  and port/adapter separation rationale.
- `plan/IMPLEMENTATION_PLAN.md` — ACT-1, ACT-2, ACT-3, VCR-014, OX-1.1–OX-1.4.
- `specs/case-management.md` — CM-01-001 (actor isolation requirement).
- `vultron/core/ports/emitter.py` — `ActivityEmitter` Protocol (OX-1.0).
- `vultron/adapters/driven/delivery_queue.py` — stub emitter adapter.
