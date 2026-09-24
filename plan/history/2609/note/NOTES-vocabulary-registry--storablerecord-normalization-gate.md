---
source: NOTES-vocabulary-registry--storablerecord-normalization-gate
timestamp: '2026-09-23T16:39:22.363843+00:00'
title: 'Archived: StorableRecord normalization gate (_NORMALIZE_WIRE_TO_CORE)'
type: note
---

Removed from `notes/vocabulary-registry.md` during #2982. The section described a
write-side normalisation gate that no longer exists.

## Why it was superseded

Issue #2940 removed write-side wire→core normalisation together with
`_NORMALIZE_WIRE_TO_CORE`, `_normalize_to_core()`, and
`test/architecture/test_normalize_wire_to_core_ratchet.py`. With
`extra="forbid"` (ARCH-12-003) a core type rejects a wire-shaped payload loudly
rather than mis-storing it, and a row that is nonetheless persisted in a wire
shape is projected on *read* by
`vultron/adapters/driven/datalayer_sqlite/hydration.py::project_wire_row_to_core`.
`_storable_to_record` in `datalayer_sqlite/crud.py` now preserves `data_`
verbatim and says so in its own docstring.

The surviving note text asserted the opposite as a MUST ("This round-trip MUST be
gated on `record.type_ in _NORMALIZE_WIRE_TO_CORE`"), which is the #2505 failure
mode: a stale instruction that reads as deliberate design.

## Archived content

(ISSUE-2283, 2026-08-17)

`_storable_to_record` in `vultron/adapters/driven/datalayer_sqlite/crud.py`
applies a `to_obj()` → `from_obj()` round-trip to convert stored
`StorableRecord` data back to its domain shape. This round-trip MUST be
gated on `record.type_ in _NORMALIZE_WIRE_TO_CORE`.

**Why**: Applying the round-trip to ALL types causes silent field loss for
subtype-specific fields. For example, storing a `VultronPerson` via
`StorableRecord(type_="Actor", data_=...)` and round-tripping through
`find_in_vocabulary("Actor")` → `as_Actor.model_validate()` drops all
`VultronPerson`-specific fields (e.g. `embargo_policy`) because the base
`as_Actor` class ignores unknown subtype fields.

**Rule**: `_NORMALIZE_WIRE_TO_CORE` is the exact set of types where core
and wire shapes are structurally incompatible (currently `CaseParticipant`
and `ParticipantStatus`). For all other types, return the verbatim `Record`
directly — either they have no vocabulary entry or their wire vocabulary
class is a faithful supertype of the stored data.

**When adding a new type to `_NORMALIZE_WIRE_TO_CORE`:**

1. The normalization round-trip is applied automatically — no further
   changes to `crud.py` required.
2. If the type is not registered in the wire vocabulary, the
   `except (ValueError, KeyError)` fallback silently skips normalization.
   Add a test to catch this when adding a new type to the set.
