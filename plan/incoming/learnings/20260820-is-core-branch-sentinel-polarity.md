---
title: "_is_core_branch sentinel: True default on VultronObject, not False"
type: learning
timestamp: '2026-08-20T14:15:00+00:00'
source: ISSUE-2416
signal: design-question
---

Issue #2416 described the `_is_core_branch` sentinel as `False` on `VultronObject` with
`True` on `CoreObject`. This polarity is wrong: `VultronObject`-direct core subclasses
(e.g. `VultronOfferRecord`) inherit from `VultronObject`, not `CoreObject`, so setting
`False` on `VultronObject` would cause those five types to be skipped by the guard and
never register in `CORE_TYPE_MAP`.

The correct polarity is `True` as the default on `VultronObject` (assume core branch
unless told otherwise) and `False` overridden on `as_Object` (wire root opts all wire
subclasses out). This way:

- `VultronObject`-direct core types: inherit `True` from `VultronObject` → register
- `CoreObject` subclasses: inherit `True` from `VultronObject` via `CoreObject` → hook
  fires, but `CoreObject.__init_subclass__` registers them in `CORE_VOCABULARY` instead
- Wire types (`as_Object` subclasses): inherit `False` from `as_Object` → skipped

The lesson: when a sentinel guards a hook on a shared root, the default must be the
value inherited by the *positive* case (core), not the exclusion case (wire).
