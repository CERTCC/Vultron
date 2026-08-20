---
title: "_normalize_to_core must skip _AS_OBJECT_REF_FIELDS in child loop"
type: learning
timestamp: "2026-08-19T21:30:00Z"
source: ISSUE-2401
signal: design-question
---

When expanding `_NORMALIZE_WIRE_TO_CORE` to include types whose wire form carries
`_AS_OBJECT_REF_FIELDS` values (e.g. `Invite.target` holding a `VulnerabilityCaseStub`),
the child normalization loop in `_normalize_to_core` must skip those fields.

`VulnerabilityCaseStub` is a minimal wire class with `type_=VulnerabilityCase` but no
`to_core()` projection — it is always dehydrated to an ID string by `_dehydrate_data`
and is never stored standalone. Calling `to_core()` on it would raise
`NotImplementedError`.

The fix: in the child loop, `continue` when `field_name in _AS_OBJECT_REF_FIELDS`.
This is safe because those fields' in-memory shape is irrelevant to the stored row.

Any future type added to `_NORMALIZE_WIRE_TO_CORE` whose wire form nests stub/reference
objects in `object_`, `target`, `origin`, `result`, or `instrument` will benefit from
this skip automatically.
