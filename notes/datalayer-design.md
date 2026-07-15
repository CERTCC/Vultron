---
title: "DataLayer Design: Architecture and Migration Notes"
status: active
tags: [datalayer, ports, persistence, architecture, migration, hexagonal]
description: >
  Architectural analysis of the DataLayer port contract, CasePersistence
  narrowing, auto-rehydration requirements, storage record design, and
  vocabulary registry entanglement. Operating rules live in
  vultron/core/ports/AGENTS.md.
related_specs:
  - specs/datalayer.yaml
  - specs/architecture.yaml
related_notes:
  - notes/domain-model-separation.md
  - notes/architecture-hexagonal.md
  - notes/activitystreams-semantics.md
relevant_packages:
  - vultron/core/ports
  - vultron/adapters/driven
  - vultron/wire/as2/vocab
---

# DataLayer Design: Architecture and Migration Notes

Operating rules summary: `vultron/core/ports/AGENTS.md`.
Specs: `specs/datalayer.yaml` (DL-01 through DL-04).

## DataLayer vs. CasePersistence

The repository distinguishes between two layers of persistence contract:

| Port | Intended callers | Purpose |
| --- | --- | --- |
| `DataLayer` | adapters, routers, infrastructure code | Full adapter-level contract, including persistence, queue operations, health/admin helpers, and diagnostics |
| `CasePersistence` | core use cases and BT nodes | Narrow core-facing persistence/query contract |
| `CaseOutboxPersistence` | the small subset of core code that also enqueues outbound activities | `CasePersistence` plus outbound enqueue methods only |

`CasePersistence` is intentionally narrower than `DataLayer`. Its current
required minimum surface is:

- `create`
- `read`
- `get`
- `save`
- `by_type`
- `find_case_by_report_id`
- `find_actor_by_short_id`

That list is the current minimum contract, not a promise that the
surface is finished forever. Future additions are allowed only when they
preserve the same core-facing persistence/query boundary. Queue methods,
health checks, admin helpers, diagnostics, and low-level storage
primitives remain part of the full `DataLayer` contract instead.

## Deprecated Compatibility Methods

`get()` and `by_type()` remain on `CasePersistence` only as compatibility
methods during the migration away from raw-record access in core. They
are deprecated and should be treated as removal targets, not stable
design endpoints.

For new or refactored core code, prefer:

- `read()` for single-object lookup
- `list_objects()` for typed collection queries
- dedicated typed helper methods when a generic query would otherwise
  expose raw persistence details

## CaseOutboxPersistence as a Smell Marker

`CaseOutboxPersistence` exists for the small amount of core code that
must both update case state and enqueue outbound activities. That need is
sometimes legitimate, but it should not become invisible. When a
`ReceivedUseCase` depends on `CaseOutboxPersistence`, treat that as an
architectural smell: the handler is mixing inbound processing with
outbound broadcast and should be reviewed for a cleaner split later.

## Auto-Rehydration: `dl.read()` MUST Return Fully Typed Objects

The DataLayer port MUST guarantee that `dl.read(id)` and
`dl.list_objects(type_key)` always return fully rehydrated, typed domain
objects — never raw storage records, untyped dicts, or objects with
dehydrated string references in nested fields.

**Rationale**: the SQLite DataLayer adapter currently dehydrates nested
object references to ID strings on write. Without auto-rehydration on
read, every use case that retrieves an activity with a nested object must
manually coerce the dehydrated string back to a typed object via
`model_validate`. That duplication:

- directly caused the INLINE-OBJ-B bugs (bare string `object_` values
  passing through to Accept/Reject constructors)
- repeats the same strip-and-validate boilerplate across multiple use
  cases
- violates the hexagonal principle that core should not know about
  storage internals

Auto-rehydration applies to **all fields that the adapter dehydrates**:

- `object_` — the primary offender (transitive activity nested object)
- `target` — target object reference
- `origin` — origin object reference
- any other field that `_dehydrate_data` currently collapses to an ID
  string

Once the DataLayer adapter implements auto-rehydration on read, all
manual coercion code in use cases MUST be removed. Search targets
include:

- `vultron/core/use_cases/triggers/embargo.py`
- `vultron/core/use_cases/triggers/report.py`
- `vultron/core/use_cases/received/sync.py`
- any other site calling `model_validate` after `dl.read()` to recover
  nested object type information

Specs: `specs/datalayer.yaml` DL-01-001 through DL-01-004.

## Core Should Reliably Get Domain Objects from DataLayer

Core should be able to call `dl.read(id)` or `dl.list(type_key)` and
receive properly typed domain objects rather than raw SQLite records,
untyped dicts, or ambiguous `StorableRecord` types.

Conversely, when persisting objects, core should be able to call
`dl.save(domain_obj)` and trust that the adapter handles the translation
to whatever storage format is needed. Core should not need to call
`object_to_record()` or know anything about storage internals.

Symptoms of an unhealthy boundary include:

- `record_to_object()` being called in core use cases to convert
  DataLayer results back into domain objects
- `object_to_record()` being called in core use cases before
  `dl.update()`
- type checks like `if isinstance(result, Document): ...` appearing in
  core, revealing DataLayer implementation details in business logic

Recommended direction:

1. `dl.read(id)` returns a typed, fully rehydrated domain object (or
   raises `VultronNotFoundError`).
2. `dl.save(obj)` accepts domain objects directly and handles all
   serialization internally.
3. `dl.list(type_key)` returns an iterable of typed, fully rehydrated
   domain objects.
4. All `object_to_record()` / `record_to_object()` calls move into the
   adapter.

A mapping layer between core objects and DataLayer records belongs in the
adapter, not in core. This improves separation of concerns and makes core
logic easier to test without mocking storage internals.

This is also why `get()` and `by_type()` are a poor long-term fit for
`CasePersistence`: they keep raw-record style access available to core
when the target direction is fully typed domain-object access.

## DataLayer Storage Records Need Re-Evaluation

`Record` and `StorableRecord` in
`vultron/adapters/driven/db_record.py` were designed when wire and core
were the same layer. Now that they are separated, these classes need
re-evaluation. The questions to answer are:

1. Should `Record`/`StorableRecord` remain as adapter-specific types, or
   should they be promoted to a more neutral abstraction?
2. Is a tiered adapter structure appropriate — a thin translation adapter
   that converts domain objects to/from a generic dict/document form,
   sitting above a storage-specific adapter (SQLite, MongoDB, SQL)?
3. How should the DataLayer port be typed: should it use generic
   `dict`/`Any` for storage records, or should there be typed protocols
   for different record kinds?

**Key principle**: the DataLayer **port** should be defined entirely in
terms of core domain objects. The DataLayer **adapter** handles all
translation to storage format. Core should be agnostic to whether the
adapter uses separate tables per type, a single JSON blob, or a document
store.

Research needed: audit all current callers of `object_to_record()`,
`record_to_object()`, and `find_in_vocabulary()` to understand the scope
of the coupling before designing the refactor.

## Vocabulary Registry Entanglement Across Wire, Core, and DataLayer

The vocabulary registry in `vultron/wire/as2/vocab/` was created before
the hexagonal architecture separated wire from core. As a result:

- `vultron/adapters/driven/db_record.py` uses the vocabulary registry to
  determine AS2 type names for storage keys.
- `vultron/wire/as2/rehydration.py` uses the vocabulary registry to
  reconstruct wire objects from DataLayer records.
- these two files create a tight coupling: the DataLayer's behaviour
  depends on the wire layer's type system.

If the wire layer is removed or replaced, the DataLayer adapter breaks.
Core cannot interact with the DataLayer in terms of core domain objects
because the adapter expects to find AS2 type names at every step.

Recommended direction:

1. The DataLayer adapter should maintain its own type-to-table mapping
   that is independent of the wire vocabulary registry.
2. Rehydration of wire objects from storage should be confined to the
   wire adapter layer, not shared with core.
3. Core's interaction with the DataLayer should use core domain type keys
   (`"VultronCase"`, `"VultronReport"`, etc.) rather than AS2 type
   names (`"Case"`, `"VulnerabilityReport"`, etc.).

This separation allows the wire layer to evolve (or be replaced) without
breaking DataLayer storage, and allows core to read/write domain objects
without knowing anything about AS2 naming conventions.

Files to investigate:

- `vultron/adapters/driven/db_record.py`
- `vultron/adapters/driven/datalayer_sqlite.py`
- `vultron/wire/as2/rehydration.py`
- `vultron/wire/as2/vocab/registry.py`

---

## `outbox_list()` Requires `clone_for_actor` in Tests

(ISSUE-1298, 2026-07-10)

`SqliteDataLayer.outbox_list()` reads the outbox for `dl._actor_id`, which is
`""` on a freshly constructed `SqliteDataLayer("sqlite:///:memory:")`. BT nodes
call `record_outbox_item(actor_id, activity_id)`, writing to the named actor's
queue. The two paths do not share the same key unless the DataLayer was obtained
via `clone_for_actor(actor_id)`.

**In tests that verify outbox contents after use-case execution:**

```python
# ✅ CORRECT — read by explicit actor ID
outbox = dl.outbox_list_for_actor(local_actor_id)

# ✅ ALSO CORRECT — clone before reading (matches BT pattern)
actor_dl = dl.clone_for_actor(actor_id)
outbox = actor_dl.outbox_list()

# ❌ WRONG — returns [] unless dl._actor_id was set
outbox = dl.outbox_list()
```

---

## Happy-Path DL Seeds Must Include Origin Activities for `dl.read()` Calls

(ISSUE-1326, 2026-07-10)

When a use case calls `dl.read(some_id)` to resolve a related entity (e.g.,
`recommender_id` from the original recommendation offer), the happy-path test
fixture MUST store that entity in the DataLayer, or the use case silently falls
back to `""` / `None`.

In `AcceptActorRecommendationReceivedUseCase` and
`RejectActorRecommendationReceivedUseCase`, the `origin` field of the inner
`Offer(CaseParticipant)` carries the original recommendation activity ID. The
use case calls `self._dl.read(recommendation_id)` to look up that activity and
extract `recommender_id`. If the activity is absent, `recommender_id=""` and the
recommender-notification branch silently no-ops — but other tree nodes still emit
to the outbox, so `len(outbox) >= 1` can pass while hiding the broken path.

**Fix pattern**: after building the inner offer with
`origin=<recommendation_id>`, also call
`dl.create(recommend_actor_activity(..., id_=<recommendation_id>))` in the
fixture so `dl.read()` resolves correctly.

**Assertion depth**: the Accept happy path emits both an Accept notification
and an Invite (2 activities). Assert `len(outbox) >= 2`, not `>= 1`, to catch
the case where only one of the two required activities was emitted.
