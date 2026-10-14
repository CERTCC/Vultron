---
source: NOTES-embargo-default-semantics--third-implicit-duration
timestamp: '2026-10-12T19:33:14.545794+00:00'
title: There was a third implicit duration, and it was the quietest
type: note
---

**Archived:** 2026-10-12
**Reason:** defect story; resolved in #3404 (EmbargoEvent.end_time is required); the rule is kept as one guidance line
**Superseded by:** vultron/core/models/embargo_event.py; EP-04-010, ARCH-10-001

---

## There was a third implicit duration, and it was the quietest

The 90-day constant and the shared key went first; one unchosen number outlived
them. `EmbargoEvent.end_time` (`vultron/core/models/embargo_event.py`) carried
`default_factory=_45_days_hence`, so **any** `EmbargoEvent` constructed without an
explicit `end_time` silently acquired 45 days — nine times the 5-day ceiling
EP-04-005 sets, and reachable from any construction site that forgot the argument.

It hid differently from the 90-day fallback. That fallback was at least reachable
by reading one function that everyone knew resolved the default. A field default
applies wherever the object is built, with no call site to inspect. EP-04-010
requires the protocol default be the *single* source of the fallback duration.

Resolved in #3404 by making `end_time` **required** rather than by pointing the
default at the protocol default: a model cannot see the actor's configuration, and
ARCH-10-001's fail-fast rule already says a required invariant is asserted at
construction. The two trigger use cases that built an event conditionally already
required `end_time` on their requests, so the only production site that leaned on
the default was the demo's replica seeding, which now resolves its duration the way
`InitializeDefaultEmbargoNode` does. Test builders state `days_from_now_utc(45)`
explicitly — the same window, now visible at every site.
