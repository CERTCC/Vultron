---
title: "Activity Factories — Design Rules"
status: active
kind: guidance
tags: [factories, wire, outbound-activities, as2]
description: >
  Design rules for the factory-function layer that wraps Vultron's internal
  ActivityStreams subclasses. Operating rules live in
  vultron/wire/as2/factories/AGENTS.md.
related_specs:
  - specs/activity-factories.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/architecture-hexagonal.md
  - notes/wire-core-boundary.md
  - notes/wire-artifact-immutability.md
relevant_packages:
  - vultron/wire/as2/factories
  - vultron/wire/as2/vocab/activities
---

# Activity Factories — Design Rules

Operating rules: `vultron/wire/as2/factories/AGENTS.md`. Spec:
`specs/activity-factories.yaml` (AF-01 through AF-09). The factory inventory is
`vultron/wire/as2/factories/__init__.py` (`__all__`); one module per domain
(`report.py`, `case/`, `embargo/`, `case_participant.py`, `actor.py`,
`sync.py`, `fault.py`) mirrors `vocab/activities/`.

## Design Rules

- **Factories return the plain AS2 base type** (`as_Offer`, not
  `_RmSubmitReportActivity`). Callers need not know Vultron's inheritance
  hierarchy.
- **Internal activity classes stay private** (leading underscore) in
  `vocab/activities/`, imported only by `factories/`. They give Pydantic runtime
  validation for free; `test/architecture/test_activity_factory_imports.py`
  enforces the boundary.
- **Build through `build_activity`** (`factories/_construct.py`), never a
  per-factory `try/except ValidationError`: one place logs and raises
  `VultronActivityConstructionError` with the cause chained, so internal class
  names stay out of public errors (AF-04-001, AF-04-003, CS-22-001). Pass the
  fields as a callable, so an argument that refuses on purpose (`_named_case`,
  `as_answered`) is reported the same way; `test_construct.py` refuses a new
  handler.
- **The act's instant is a required `at`**: every factory, and every port
  method that builds an activity, takes it, and `build_activity` alone writes it
  as `published` and `updated`, so the signer's `authored_time` always has one
  (ADR-0176). A rebuilt embed that must not carry a time drops it with
  `model_copy` after the build (`_rebuilt_recommendation`).
- **Factories build from primitives**, never from a dump of a domain object.
- **Tests import from `vultron.wire.as2.factories`**, as all external code does.
  Examples: `test/wire/as2/factories/`.

## Render Core Objects Through the Port, Never Dump-and-Revalidate

Do not convert a core object to a wire class with
`wire_cls.model_validate(core_obj.model_dump(...))`. A dump/revalidate round trip
has nowhere to record that a field differs in type or name between the two
sides, so it fails with a `ValidationError` that does not name the wrong
conversion path. A paired domain type needs no conversion at all: its wire shape
is the core object's own aliased dump, produced by `WireRenderPort` (ARCH-20-001,
ARCH-20-002). `from_core()` and `_field_map` on the wire base classes are this
same round trip; do not add new overrides or callers. See
[core-wire-rendering-port](core-wire-rendering-port.md).

## Pass the Domain Object, Not a Hand-Built Stub

When a factory parameter is a domain entity whose fields decide how the wire
object is enriched, pass the complete domain object and let the factory derive
the enrichment; never pre-build a partial stub in the adapter. A hand-built
stub silently omits fields the object would have supplied: an adapter-built
case stub once carried only the embargo URI, dropping the terms CM-17-002
requires. Rules: AF-01-005 to AF-01-007.
