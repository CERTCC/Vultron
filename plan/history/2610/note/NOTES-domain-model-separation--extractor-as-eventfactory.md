---
source: NOTES-domain-model-separation--extractor-as-eventfactory
timestamp: '2026-10-12T19:32:40.487572+00:00'
title: 'Extractor as EventFactory: Centralizing AS2-to-Domain Mapping'
type: note
---

**Archived:** 2026-10-12
**Reason:** not pursued — design option parked; the user chose to archive it without filing an Idea issue (epic #4492, notes sweep #4496)
**Superseded by:** vultron/wire/as2/extractor/; vultron/core/models/events/

---

## Extractor as EventFactory: Centralizing AS2→Domain Mapping

TECHDEBT-30 added domain-specific property getters to event subclasses via
`_mixins.py`. The next evolution is to have the extractor produce
domain-specific event objects directly, rather than a generic event that
then exposes typed properties through mixin aliases.

**Current state**: `extractor.py` maps `(AS2 Activity type, Object type)` to
`MessageSemantics`, and the semantic registry routes each semantics value to
its typed `FooReceivedEvent` subclass. Per-semantic subclasses carry
domain-named property aliases where the AS2→domain mapping is non-obvious.
The discriminated event hierarchy that this builds on is delivered in
`vultron/core/models/events/` (design history archived under
`plan/history/2609/note/NOTES-domain-model-separation--domain-events-bridge.md`).

**Design option — EventFactory pattern**: Rather than having the extractor
only classify the activity, it could also perform the field translation and
return a type-specific domain event. Two equivalent approaches:

- `Activity.to_domain()` — an instance method on AS2 activity models that
  returns the appropriate domain event subclass.
- `EventFactory` — a standalone translator that takes an AS2 activity,
  determines the semantics (as the extractor does now), and constructs a
  domain event object with fully domain-named fields.

The domain event then becomes the direct input to its corresponding use case,
making the use case's field access completely free of AS2 naming.

**Key principles for implementation**:

- Use `extractor.py`'s `ActivityPattern` definitions as the authoritative
  reference for how AS2 fields map to semantic roles. Centralise this mapping
  in one place rather than scattering AS2 field name handling across use cases.
- Core objects MUST be ignorant of AS2: they must not import from
  `vultron/wire/as2/` or reference `as_*` field names.
- Apply DRY: a single mapping dict or factory function per semantics type
  is preferable to per-use-case translation code.

**Implementation note**: `VultronEvent` may be too generic as a single base
class if use cases are expected to reliably infer field semantics from it.
Per-semantic subclasses (delivered in `vultron/core/models/events/`) combined
with the EventFactory approach give both type safety and domain clarity.

**See also**: `specs/semantic-extraction.yaml`, `specs/code-style.yaml` CS-10-002
(`FooActivity` vs `FooEvent` naming), and `vultron/core/models/events/` for the
delivered discriminated event hierarchy.
