---
title: "CS_vf and CS_d should be StrEnum to match their leaf component enums"
type: learning
timestamp: "2026-08-28T00:00:00Z"
source: ISSUE-2662
signal: design-question
---

`VendorAwareness`, `FixReadiness`, and `FixDeployment` — the leaf component
enums of the VFD state model — are already `StrEnum`. The compound enums
`CS_vf` and `CS_d` were initially implemented as regular `Enum` with
`VfState`/`DState` NamedTuple values, making `.value` return a tuple and
requiring `.name` for string access.

Converting them to `StrEnum` (values `"vf"`, `"Vf"`, `"VF"`, `"d"`, `"D"`)
aligns them with their leaf components and makes `.value` the canonical string.
Side effects to fix:

1. `cs_event_label()` in `narrative_log.py` used `after.value._fields` (NamedTuple API)
   — must dispatch on `hasattr(value, '_fields')` and use character-level comparison
   for StrEnum dimensions.
2. Dead tuple-coercion branches in `_coerce_vf`/`_coerce_d` (`dimensions.py`) must
   be removed.
3. `is_monotonic_vf_forward`/`is_monotonic_d_forward` call `_is_monotonic_forward(source.value, dest.value)`
   — with StrEnum, `source.value` is a string; `zip(str1, str2)` character-pairs work
   correctly because the naming convention encodes monotonicity (lowercase=unset,
   uppercase=set).

## Audit disposition (2026-09-02)

Resolved. CS_vf and CS_d are StrEnum as of vultron/core/states/cs.py:259 and :270.
