---
source: NOTES-datalayer-design--core-domain-objects
timestamp: '2026-09-17T17:19:54.464476+00:00'
title: Core Should Reliably Get Domain Objects from DataLayer
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) delivered; rule in vultron/core/ports/AGENTS.md:73; core no longer calls record/object converters
**Superseded by:** vultron/core/ports/AGENTS.md; specs/datalayer.yaml DL-05

---

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
