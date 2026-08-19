---
title: CORE_TYPE_MAP registration hook belongs on VultronObject, not CoreObject
type: learning
timestamp: 2026-08-19T00:00:00Z
source: ISSUE-1992
signal: design-question
---

When fixing ARCH-12-003 (#1992), the initial plan was to register core-layer
types in `CORE_TYPE_MAP` via `CoreObject.__init_subclass__`. This worked for
`CoreActor` (which IS a `CoreObject` subclass) but missed 5 of the 6 affected
types (`VultronOfferRecord`, `VultronPendingCaseInbox`,
`PendingCreateCaseActivity`, `VultronReportCaseLink`,
`VultronReplicationState`) because they inherit from `VultronObject` directly,
not from `CoreObject`.

**Root cause:** The VultronObject → CoreObject branching means the two
hierarchies share only `VultronObject` as common root. Any hook that needs to
cover both must live on `VultronObject`, not `CoreObject`.

**Fix:** Placed the `CORE_TYPE_MAP` registration hook in
`VultronObject.__init_subclass__` using the same "concrete Literal type_
annotation" guard as `CoreObject`. `CoreObject` also registers no-annotation
subclasses by class name (for the `_set_type_from_class_name` path) since
`CoreObject` is the only branch that has that validator.
