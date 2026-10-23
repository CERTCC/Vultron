---
title: "as_Object needs explicit validate_assignment=False to block cross-branch MRO contamination"
type: learning
timestamp: '2026-08-19T00:00:00+00:00'
source: ISSUE-2294
signal: design-question
---

## Decision

When applying `ValidatedAssignmentMixin` (which sets `validate_assignment=True`) to
`VultronObject`, the cross-branch MRO coupling `as_Object(as_Base, VultronObject)`
propagates the flag to all 65 wire vocabulary classes — violating ARCH-12-002 (wire
branch must stay lenient for inbound AS2 data).

The chosen fix: add an explicit `model_config = ConfigDict(validate_assignment=False)` to
`as_Object` in `vultron/wire/as2/vocab/base/objects/base.py`. Pydantic v2 merges
`model_config` dicts in MRO order with the most-derived class winning, so this override
cancels the inherited `True` at the wire boundary.

**Alternative rejected**: replacing `VultronObject` in `_VALIDATE_ASSIGNMENT_TARGETS` with
`CoreObject` + individual classes that cover VultronObject's core-only descendants. This
would have required more ratchet-test churn and left `VultronObject` itself uncovered by
any named target, which the coverage test would have flagged.

## Why this matters for future work

Any future `model_config` change on `VultronObject` will propagate across the
`as_Object` MRO unless explicitly overridden there. The `as_Object` config override
is load-bearing infrastructure — it must be preserved (or extended, not removed) by
any change to `VultronObject.model_config`.

The broader fragility (cross-branch MRO coupling at `as_Object`) is tracked by
issues #2288/#2289 (the `alias_generator=to_camel` contamination, same root cause).
Full resolution requires completing the ADR-0017 wire→core separation.

## Secondary discovery

`ValidatedAssignmentMixin` itself is picked up by `_core_model_classes()` in the ratchet
test (it lives in `vultron/core/models/base`, inherits `BaseModel`, and the scanner has no
mixin-exclusion logic). The fix was to add it to `_VALIDATE_ASSIGNMENT_TARGETS` — it is
its own covered root, trivially satisfying the coverage invariant.

**Promoted**: 2026-08-24 — captured in notes/core-wire-rendering-port.md + vultron/wire/as2/vocab/AGENTS.md.
Docs PR: [PR URL TBD].
