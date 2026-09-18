---
title: "Domain Model Separation: Wire, Domain, and Persistence"
status: active
description: >
  Analysis of wire/domain/persistence model coupling in VulnerabilityCase and
  recommended separation path.
related_specs:
  - specs/architecture.yaml
  - specs/case-management.yaml
  - specs/datalayer.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/case-state-model.md
  - notes/datalayer-design.md
relevant_packages:
  - pydantic
  - vultron/wire/as2
  - vultron/core/models
  - vultron/adapters
---

# Domain Model Separation: Wire, Domain, and Persistence

## Outbound Event Design Questions (P65-6 Considerations)

Before implementing the outbound path (domain event → AS2 activity), consider:

- **Which events go in `core/models/`?** Domain events corresponding to
  outbound activities (e.g., `CaseCreatedEvent`, `EmbargoProposedEvent`).
  These are distinct from inbound received events.
- **Outbound serializer mapping**: Should `wire/as2/serializer.py` map each
  domain event type to AS2 one-to-one, or via a generic mapping table?
  One-to-one is safer for type checking; a table is more compact.
- **Interplay with the outbox pipeline**: Domain events emitted by handlers
  must eventually become AS2 activities written to the actor outbox. The
  serializer is the seam between these two concerns (see `specs/outbox.yaml`).
- **ADR**: Consider drafting an ADR for the domain/wire separation decision
  before implementation, to record the rationale. See `docs/adr/_adr-template.md`.

## Cross-References

- `specs/case-management.yaml` CM-03-006 — `case_statuses` rename requirement
- `specs/code-style.yaml` CS-10-001 — typed Pydantic objects at port/adapter boundaries
- `specs/code-style.yaml` CS-10-002 — `FooActivity` vs `FooEvent` naming convention
- `specs/datalayer.yaml` — DataLayer port requirements (auto-rehydration, type-safe writes)
- `notes/datalayer-design.md` — DataLayer design notes (auto-rehydration decision,
  storage record evaluation, vocabulary registry entanglement)
- `notes/case-state-model.md` — CaseStatus/ParticipantStatus append-only
  history model
- `notes/activitystreams-semantics.md` — `case_activity` type limitation,
  Accept/Reject `object_` field patterns
- `notes/use-case-behavior-trees.md` — use case/BT layering and mapping from
  protocol activities to use cases
- `AGENTS.md` — pitfalls for `case_activity`, `active_embargo`,
  and `case_status` (singular) field
- `docs/adr/_adr-template.md` — template for future ADR on this separation

---

## Wire-Layer Terminology Leaking into Core Event Interfaces

Several core use cases and trigger handlers receive event objects whose field
names (`object`, `target`, `context`, `actor`) are mapped directly from the
AS2 specification rather than using domain-meaningful names. For example, when
an Offer of a report is received, the use case should receive a field named
`report_id` rather than `object_id`. When a note is added to a case, the use
case should receive a `case_id` field rather than a generic `target_id`.

This leakage undermines the hexagonal architecture principle that the core
domain should be expressed in domain vocabulary. It also increases the
cognitive overhead for developers who must mentally translate between AS2
semantics and domain intent when reading core business logic.

**Recommended approach:** For each received-event subtype, ensure that all
fields use domain-appropriate names. Where the AS2 mapping is non-obvious,
add a comment or alias. New event subtypes introduced for Priority 90 and
beyond should follow domain naming from the start.

**Reference:** `specs/architecture.yaml` ARCH-09 (core MUST NOT leak wire
concerns); `specs/code-style.yaml` CS-12-001 (domain vocabulary in class names).

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

---
