---
source: NOTES-datalayer-design--auto-rehydration
timestamp: '2026-09-17T17:19:54.179052+00:00'
title: 'Auto-Rehydration: dl.read() MUST Return Fully Typed Objects'
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) auto-rehydration delivered; rule now in vultron/core/ports/AGENTS.md:74
**Superseded by:** specs/datalayer.yaml DL-01; vultron/core/ports/AGENTS.md

---

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
