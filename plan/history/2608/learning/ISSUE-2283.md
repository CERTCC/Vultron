---
title: _storable_to_record must gate normalization on _NORMALIZE_WIRE_TO_CORE to avoid data loss
type: learning
timestamp: '2026-08-17T00:00:00+00:00'
source: ISSUE-2283
signal: design-question
---

The initial fix for #2283 applied the `to_obj()` → `from_obj()` round-trip to ALL
`StorableRecord` types.  This caused a regression in
`test_datalayer_get_actors_includes_embargo_policy`: storing a `VultronPerson`
(subclass of `as_Actor`) via `StorableRecord(type_="Actor", data_=...)` silently
lost the `embargo_policy` field because `find_in_vocabulary("Actor")` returns the
*base* `as_Actor` class, and `model_validate()` against the base class drops
subtype-specific fields.

**Decision**: Gate the normalization round-trip on `record.type_ in
_NORMALIZE_WIRE_TO_CORE`.  For types outside that set, return the verbatim
`Record` directly.  This is safe because `_NORMALIZE_WIRE_TO_CORE` is exactly the
set of types where core and wire shapes are structurally incompatible (currently
`CaseParticipant` and `ParticipantStatus`); all other types either have no
vocabulary entry or their wire vocabulary class is a faithful supertype of the
stored data.

**Implication for future migrations**: When a new type is added to
`_NORMALIZE_WIRE_TO_CORE`, the `create()` / `update()` normalisation is
automatically applied with no further changes to `crud.py`.  However, if the type
is not registered in the wire vocabulary, the `except (ValueError, KeyError)`
fallback silently skips normalisation — add a test when adding a new type to the
set.

**Promoted**: 2026-08-24 — captured in notes/vocabulary-registry.md.
Docs PR: [PR URL TBD].
