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
`specs/activity-factories.yaml` (AF-01 through AF-08). The factory inventory is
`vultron/wire/as2/factories/__init__.py` (`__all__`); one module per domain
(`report.py`, `case.py`, `embargo.py`, `case_participant.py`, `actor.py`,
`sync.py`, `fault.py`) mirrors `vocab/activities/`.

## Design Rules

- **Factories return the plain AS2 base type** (`as_Offer`, not
  `_RmSubmitReportActivity`). Callers need not know Vultron's inheritance
  hierarchy.
- **Internal activity classes stay private** (leading underscore) in
  `vocab/activities/`, imported only by `factories/`. They give Pydantic runtime
  validation for free; `test/architecture/test_activity_factory_imports.py`
  enforces the boundary.
- **Wrap validation failures**: catch `ValidationError`, raise
  `VultronActivityConstructionError` with the original as `__cause__`
  (`factories/errors.py`), so internal class names stay out of public errors.
- **Factories build from primitives**; `from_core()` converts an existing domain
  object and is a separate concern.
- **Tests import from `vultron.wire.as2.factories`**, as all external code does.
  Examples: `test/wire/as2/factories/`.

## Convert Through the Declared Field Map, Never Dump-and-Revalidate

Do not convert a core object to a wire class with
`wire_cls.model_validate(core_obj.model_dump(...))`. A dump/revalidate round trip
has nowhere to record that a field differs in type or name between the two
sides, so it fails with a `ValidationError` that does not name the wrong
conversion path. Use `from_core()`, whose `_field_map` and
`_strip_core_context` (`vultron/wire/as2/vocab/objects/base.py`) declare the
per-field mapping. See [wire-core-boundary](wire-core-boundary.md).

## Pass the Domain Object, Not a Hand-Built Stub

When a factory parameter is a domain entity whose fields decide how the wire
object is enriched, pass the complete domain object and let the factory derive
the enrichment; never pre-build a partial stub in the adapter. A hand-built
stub silently omits fields the object would have supplied: an adapter-built
case stub once carried only the embargo URI, dropping the `end_time` CM-17-002
requires. Rule: AF-01-005.
