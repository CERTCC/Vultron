---
source: CONCERN-586
timestamp: '2026-06-03T18:01:15.014148+00:00'
title: VultronActivity.object_ dict round-trip bypass
type: learning
---

## Category

Type safety / architecture

## Severity

Medium — currently worked around but fragile

## Evidence

`VultronActivity.object_` is `Any | None` (line 56 of `vultron/core/models/activity.py`).
When `_load_outbound_activity()` round-trips a typed wire-layer activity
(`_RmEngageCaseActivity`) through `model_dump()` → `VultronActivity.model_validate()`,
the nested `VulnerabilityCase` model becomes a plain dict. This caused `dl.hydrate()`
to be skipped entirely in the outbox handler, leading to #585/#572/#573/#574.

A targeted dict-recovery workaround was added in PR #577, but it only handles types
listed in `_STUB_OBJECT_TYPES` and relies on re-reading from the DataLayer.

## Impact

- Fragile: any new object type that needs hydration must be added to `_STUB_OBJECT_TYPES`
- The root issue is that wire-layer types (`VulnerabilityCase`, `VulnerabilityReport`,
  `CaseParticipant`) inherit from `as_Object` (wire base), not `VultronObject` (core base).
  Both are `BaseModel` subclasses but have no common Vultron-specific ancestor.
- Narrowing `object_` to `BaseModel | None` breaks Pydantic validation because
  the round-trip produces dicts, not BaseModel instances.

## Suggested action

Consider whether wire-layer objects should be projections of core objects into AS2
vocabulary, sharing a common abstract base. Alternatively, use a discriminated union
or custom validator that can reconstruct typed models from dicts during validation.
This is an architectural decision that may warrant an ADR.

**Resolved**: 2026-06-03 — root cause is domain objects placed in `wire/as2/vocab/objects/`
instead of `core/models/`. The correct fix is to migrate those objects to core and type
`VultronActivity.object_` as a Pydantic discriminated union. Implementation tracked in #699.
Docs PR: [#700](https://github.com/CERTCC/Vultron/pull/700).
