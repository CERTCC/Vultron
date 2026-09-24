---
source: NOTES-domain-model-separation--domain-events-bridge
timestamp: '2026-09-17T17:22:00.683452+00:00'
title: Domain events as the bridge (delivered)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) delivered in vultron/core/models/events/; naming normative in CS-10-002; P65-3/P65-6a self-marked Complete
**Superseded by:** vultron/core/models/events/; specs/code-style.yaml CS-10-002; vultron/semantic_registry/

---

## Domain Events as the Bridge Between Core and Wire

When removing AS2 wire types from `core/behaviors/` (P65-6), the recommended
pattern is **per-semantic domain event types** rather than a single generic
`VultronEvent` class that mirrors the AS2 structure.

The key insight: domain events only need to be defined for the things that
are represented by use cases — items corresponding to `MessageSemantics`
values or triggerable behaviors. Define specific named event classes such as
`ReportSubmittedEvent`, `CaseCreatedEvent`, `EmbargoAcceptedEvent` rather
than one large generic type. Each event class carries exactly the fields
needed for its specific use case.

This approach:

- Makes the translation point (wire → domain, domain → wire) explicit per
  semantic type, rather than generic
- Supports the use-case-as-port pattern: adapters translate from AS2 activity
  to a specific domain event, and from a domain event back to AS2 for outbound
- Avoids duplicating the full AS2 structure in the core while still retaining
  rich semantic information
- Aligns the domain model with the `MessageSemantics` vocabulary, making the
  relationship between wire format and domain intent explicit

These domain event types belong in `core/models/` alongside `MessageSemantics`.
The outbound serializer in `wire/as2/serializer.py` will map each domain event
type to the appropriate AS2 activity type.

### Naming Convention

Wire-level and domain-level types MUST use distinct suffixes to prevent
accidental coupling (see `specs/code-style.yaml` CS-10-002):

- Wire layer (`vultron/wire/as2/vocab/activities/`): `FooActivity` — the
  structured AS2 payload the extractor recognizes (e.g., `ReportSubmitActivity`)
- Domain layer (`vultron/core/models/events/`): `FooEvent` — the typed
  domain event handlers and use cases consume (e.g., `ReportSubmittedEvent`)
  - Received-message flavour: `FooReceivedEvent` (remote actor did something)
  - Trigger flavour: `FooTriggerEvent` (local actor initiated an action)

The `events/` directory structure under `core/models/` SHOULD mirror the
`activities/` directory structure under `wire/as2/vocab/`, with submodules
grouped by semantic category (`report.py`, `case.py`, `embargo.py`, etc.).

### Discriminated Event Hierarchy (P65-3 — Complete)

**Status: implemented.** All 50 `MessageSemantics` values have a typed
`FooReceivedEvent` subclass in `vultron/core/models/events/`. Each subclass
carries `semantic_type: Literal[MessageSemantics.XYZ]` as a discriminator and
domain-named property aliases where the AS2→domain mapping is non-obvious.

The `vultron/semantic_registry/` wires each semantics entry to its typed
subclass via `SemanticEntry.event_class`; `extract_event()` returns the
narrowed subclass directly — no raw `VultronEvent` field access is needed in
handlers.

The base `VultronEvent` (in `vultron/core/models/events/base.py`) carries:

```python
class VultronEvent(BaseModel):
    semantic_type: MessageSemantics  # discriminator field
    activity_id: str
    actor_id: str
    # rich domain object fields (object_, target, context, origin, ...)
    # derived ID/type properties (.object_id, .target_id, ...)
```

Specific subclasses extend this with domain-named properties (e.g. `.case_id`,
`.report_id`) derived from the base fields.

Completed migration steps (all four now done):

1. ✅ Audited all handler field accesses (P65-3 audit).
2. ✅ Enriched base `VultronEvent` with the needed fields.
3. ✅ Defined per-semantic subclasses for all 50 `MessageSemantics` values.
4. ✅ `extract_event()` produces the typed subclass for every inbound activity.

### P65-6a: `extract_intent()` Returns a Typed Subclass (Complete)

**Status: implemented.** `extract_intent()` (in `vultron/wire/as2/extractor/_extract.py`)
takes `event_class: type[VultronEvent]` and instantiates it directly. The public
`extract_event()` in `vultron/semantic_registry/__init__.py` looks up the
typed subclass from the registry and calls `extract_intent()` with it, so the
return value is always the narrowed per-semantic subclass.

Implementation details:

- `VultronEvent` base class lives in `core/models/events/base.py` with
  `semantic_type: MessageSemantics` as the discriminator field.
- Per-semantic subclasses live in `core/models/events/` grouped by category
  (`report.py`, `case.py`, `embargo.py`, etc.) following the `FooReceivedEvent`
  suffix convention for inbound handler-side events (see CS-10-002).
- The wire layer adapter populates the correct subclass from the raw AS2
  activity; core handlers never see AS2 types.
