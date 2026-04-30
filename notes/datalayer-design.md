---
title: DataLayer Design Notes
status: active
description: >
  Design guidance for the DataLayer port and its adapters; auto-rehydration
  contract, storage record evaluation.
related_specs:
  - specs/datalayer.yaml
related_notes:
  - notes/domain-model-separation.md
relevant_packages:
  - vultron/adapters/driven
  - vultron/core/ports
---

# DataLayer Design Notes

Design guidance for the `DataLayer` port and its adapters. Covers the
auto-rehydration contract, storage record evaluation, and vocabulary registry
coupling. See also `notes/domain-model-separation.md` for the broader
wire/domain/persistence separation context.

---

## DataLayer vs. CasePersistence

The repository now distinguishes between two layers of persistence contract:

| Port | Intended callers | Purpose |
| --- | --- | --- |
| `DataLayer` | adapters, routers, infrastructure code | Full adapter-level contract, including persistence, queue operations, health/admin helpers, and diagnostics |
| `CasePersistence` | core use cases and BT nodes | Narrow core-facing persistence/query contract |
| `CaseOutboxPersistence` | the small subset of core code that also enqueues outbound activities | `CasePersistence` plus outbound enqueue methods only |

### Current boundary

`CasePersistence` is intentionally narrower than `DataLayer`. Its current
required minimum surface is:

- `create`
- `read`
- `get`
- `save`
- `by_type`
- `find_case_by_report_id`
- `find_actor_by_short_id`

That list is the current minimum contract, not a promise that the surface is
finished forever. Future additions are allowed only when they preserve the same
core-facing persistence/query boundary. Queue methods, health checks, admin
helpers, diagnostics, and low-level storage primitives remain part of the full
`DataLayer` contract instead.

### Deprecated compatibility methods

`get()` and `by_type()` remain on `CasePersistence` only as compatibility
methods during the migration away from raw-record access in core. They are now
deprecated and should be treated as removal targets, not stable design
endpoints.

For new or refactored core code, prefer:

- `read()` for single-object lookup
- `list_objects()` for typed collection queries
- dedicated typed helper methods when a generic query would otherwise expose
  raw persistence details

The cleanup task is tracked in `plan/IMPLEMENTATION_PLAN.md` as
`TASK-CP-CLEANUP`.

### CaseOutboxPersistence as a smell marker

`CaseOutboxPersistence` exists for the small amount of core code that must both
update case state and enqueue outbound activities. That need is sometimes
legitimate, but it should not become invisible. When a `ReceivedUseCase`
depends on `CaseOutboxPersistence`, treat that as an architectural smell: the
handler is mixing inbound processing with outbound broadcast and should be
reviewed for a cleaner split later.

---

## Auto-Rehydration: `dl.read()` MUST Return Fully Typed Objects

### Design Decision (April 2026)

The DataLayer port MUST guarantee that `dl.read(id)` and
`dl.list_objects(type_key)`
always return **fully rehydrated, typed domain objects** — never raw storage
records, untyped dicts, or objects with dehydrated string references in nested
fields.

**Rationale**: The SQLite DataLayer adapter
(`vultron/adapters/driven/datalayer_sqlite.py`) currently dehydrates nested
object references to ID strings on write (via `_dehydrate_data` in
`vultron/adapters/driven/db_record.py`). Without auto-rehydration on read, every
use case that retrieves an activity with a nested object must manually coerce
the dehydrated string back to a typed object via `model_validate`. This
coercion pattern:

- Was the direct cause of the INLINE-OBJ-B bugs (bare string `object_` values
  passing through to Accept/Reject constructors).
- Duplicates the same strip-and-validate boilerplate across multiple use cases
  (`triggers/embargo.py`, `triggers/report.py`, `received/sync.py`).
- Violates the hexagonal principle that core should not know about storage
  internals.

### Scope

Auto-rehydration applies to **all fields that the adapter dehydrates**:

- `object_` — the primary offender (transitive activity nested object)
- `target` — target object reference
- `origin` — origin object reference
- Any other field that `_dehydrate_data` currently collapses to an ID string

### Migration: Remove Manual Coercion

Once the DataLayer adapter implements auto-rehydration on read, all manual
coercion code in use cases MUST be removed. Search targets:

- `vultron/core/use_cases/triggers/embargo.py` — dehydration-aware coercion of
  stored `as_Invite` to `EmProposeEmbargoActivity`
- `vultron/core/use_cases/triggers/report.py` — `_resolve_offer_and_report`
  coercion of stored offer to `RmSubmitReportActivity`
- `vultron/core/use_cases/received/sync.py` — `CaseLogEntry.from_core(entry)`
  coercion before passing to `RejectLogEntryActivity`
- Any other site calling `model_validate` after `dl.read()` to recover nested
  object type information

**Implementation task**: `DL-REHYDRATE` in `plan/IMPLEMENTATION_PLAN.md`.

**Spec**: `specs/datalayer.yaml` DL-01-001 through DL-01-004.

---

## Core Should Reliably Get Domain Objects from DataLayer

The core domain logic is frequently required to inspect what type of object
was returned from the DataLayer and branch on that, which is a sign that the
DataLayer port and adapter are not providing sufficient type guarantees. Core
should be able to call `dl.read(id)` or `dl.list(type_key)` and receive
properly-typed domain objects rather than raw SQLite records, untyped dicts,
or ambiguous `StorableRecord` types.

Conversely, when persisting objects, core should be able to call
`dl.save(domain_obj)` and trust that the adapter handles the translation to
whatever storage format is needed. Core should not need to call
`object_to_record()` or know anything about storage internals.

**Symptoms in current code:**

- `record_to_object()` is called in core use cases to convert DataLayer
  results back into domain objects — this conversion belongs in the adapter.
- `object_to_record()` is called in core use cases before `dl.update()` —
  this serialization belongs in the adapter.
- Type checks like `if isinstance(result, Document): ...` appear in core,
  revealing DataLayer implementation details in business logic.

**Recommended approach:** Refactor the `DataLayer` port and SQLite adapter so
that:

1. `dl.read(id)` returns a typed, fully rehydrated domain object
   (or raises `VultronNotFoundError`).
2. `dl.save(obj)` accepts domain objects directly and handles all
   serialization internally.
3. `dl.list(type_key)` returns an iterable of typed, fully rehydrated domain
   objects.
4. All `object_to_record()` / `record_to_object()` calls move into the adapter.

A mapping layer between core objects and DataLayer records belongs in the
adapter, not in core. This improves separation of concerns and makes core
logic easier to test without mocking storage internals.

**See also:** Datalayer Storage Records section below.

This is also why `get()` and `by_type()` are a poor long-term fit for
`CasePersistence`: they keep raw-record style access available to core when the
target direction is fully typed domain-object access.

---

## Datalayer Storage Records Need Re-Evaluation

`Record` and `StorableRecord` in `vultron/adapters/driven/db_record.py` were
designed when wire and core were the same layer. Now that they are separated,
these classes need re-evaluation. The questions to answer are:

1. Should `Record`/`StorableRecord` remain as adapter-specific types, or
   should they be promoted to a more neutral abstraction?
2. Is a tiered adapter structure appropriate — a thin translation adapter that
   converts domain objects to/from a generic dict/document form, sitting above
   a storage-specific adapter (SQLite, MongoDB, SQL)?
3. How should the DataLayer port be typed: should it use generic
   `dict`/`Any` for storage records, or should there be typed protocols for
   different record kinds?

**Key principle:** The DataLayer **port** should be defined entirely in terms
of core domain objects. The DataLayer **adapter** handles all translation to
storage format. Core should be agnostic to whether the adapter uses separate
tables per type, a single JSON blob, or a document store.

**Research needed:** Audit all current callers of `object_to_record()`,
`record_to_object()`, and `find_in_vocabulary()` to understand the scope of
the coupling before designing the refactor.

---

## Vocabulary Registry Entanglement Across Wire, Core, and DataLayer

The vocabulary registry in `vultron/wire/as2/vocab/` was created before the
hexagonal architecture separated wire from core. As a result:

- `vultron/adapters/driven/db_record.py` uses the vocabulary registry to
  determine AS2 type names for storage keys.
- `vultron/wire/as2/rehydration.py` uses the vocabulary registry to
  reconstruct wire objects from DataLayer records.
- These two files create a tight coupling: the DataLayer's behaviour depends
  on the wire layer's type system.

**Problem:** If the wire layer is removed or replaced, the DataLayer adapter
breaks. Core cannot interact with the DataLayer in terms of core domain objects
because the adapter expects to find AS2 type names at every step.

**Recommended approach:**

1. The DataLayer adapter should maintain its own type-to-table mapping that is
   independent of the wire vocabulary registry.
2. Rehydration of wire objects from storage should be confined to the wire
   adapter layer, not shared with core.
3. Core's interaction with the DataLayer should use core domain type keys
   (`"VultronCase"`, `"VultronReport"`, etc.) rather than AS2 type names
   (`"Case"`, `"VulnerabilityReport"`, etc.).

This separation allows the wire layer to evolve (or be replaced) without
breaking DataLayer storage, and allows core to read/write domain objects
without knowing anything about AS2 naming conventions.

**Files to investigate:** `vultron/adapters/driven/db_record.py`,
`vultron/adapters/driven/datalayer_sqlite.py`,
`vultron/wire/as2/rehydration.py`,
`vultron/wire/as2/vocab/registry.py`.
