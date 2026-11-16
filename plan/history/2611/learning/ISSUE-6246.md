---
title: >-
  When a message needs a fact its object does not hold, the first option is to add
  the field to the object; projections, side records and new wrapper objects come
  second
type: learning
timestamp: "2026-11-16T18:05:00Z"
source: ISSUE-6246
signal: theme-candidate
---

**Trigger.** A wire form needs to state a change to an object, and the fact that
changes lives somewhere else (a register entry, a side table, a computed view).

**Claim.** The maintainer's default is that an object stores the facts about
itself, so the message can be an `Update` of that object and nothing is held twice.
Options that leave the fact where it is (project it onto the wire form, make the
side record addressable, carry it on the activity) each duplicate the fact or
invent an object, and need a rule to keep copies consistent.

**Evidence.** Planning #6246: an embargo's status lived on the case's register
entry, not on `EmbargoEvent`. The plan offered three options that all kept it there.
The maintainer called it absurd that changing `EmbargoEvent` to carry its own fields
was not offered, and chose it (ADR-0202, PR #6479).

**How to apply.** Before listing where a fact should live, ask whether the object
the message is about should own the field, and lead with that option. A stored
schema change is acceptable when the maintainer decides it. The design rule is in
`notes/activitystreams-semantics.md` § "Choosing AS2 Terms" (PR #6479).

**What would confirm it.** Another plan where a side-record option is offered first
and the maintainer redirects to extending the object.

**Already closed**: 2026-11-16 — already in notes/activitystreams-semantics.md § Choosing AS2 Terms (PR #6479).
Docs PR: https://github.com/CERTCC/Vultron/pull/6528.
