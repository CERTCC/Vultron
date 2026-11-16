---
source: NOTES-case-event-history--an-event-is-a-state-change-not-a-message
timestamp: '2026-11-16T18:30:55.734990+00:00'
title: An Event Is a State Change, Not a Message
type: note
---

**Archived:** 2026-11-16
**Reason:** redundant — captured in CEH-04-001, CEH-04-012 to CEH-04-016 and ADR-0174; the code is vultron/measure/history/

---

## An Event Is a State Change, Not a Message

Derive a report-management, fix-path, deployment or public-state event by comparing
an entry's state against the state already reached, and name the entry's semantic
type as the event's cause (CEH-04-001).

A table keyed on the semantic type alone misses acts. One report-management move has
several wire forms: accepting a stub Invite seats the joiner at Received (CM-11-001),
answering a Full-Case Invite records Valid, Invalid or Closed (CM-11-011), a status
update reports any move, and a `Leave` drives the leaver to Closed through every
intermediate step (CM-23-022). A table that listed `Add(ParticipantStatus)` and
stopped would report no intake events for a joiner at all.

State comparison also gets the count right, because it emits nothing for an entry
that re-reports a state already reached (CEH-04-013) and one event per step for an
entry that records several at once (CEH-04-012). A case closure is **not** such an
entry: CM-23-022 commits one entry per report-management transition, so the leaver's
`V → D → C` is three entries. The genesis entry is the real example — it seats the
CASE_MANAGER's own participant at Received, Valid and Accepted together.

Two things state comparison sees that are not events. An entry may carry a whole
participant object as a *recommendation* for an actor not yet in the case, at
`RM.START`, several entries before that actor's real record exists; deriving from it
would date the actor's first event to before it was invited (CEH-04-014). And an entry
may name a state *behind* the one already reached, which is a change but not a forward
one — it is excluded from the events and reported, never emitted as a backward step
(CEH-04-015, CEH-04-016).
