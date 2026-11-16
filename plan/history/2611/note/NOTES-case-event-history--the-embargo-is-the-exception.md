---
source: NOTES-case-event-history--the-embargo-is-the-exception
timestamp: '2026-11-16T18:30:56.845889+00:00'
title: The Embargo Is the Exception
type: note
---

**Archived:** 2026-11-16
**Reason:** redundant — captured in CEH-04-005, CEH-04-008, CEH-04-009 and ADR-0174

---

## The Embargo Is the Exception

Embargo start, embargo exit and a participant's consent answer are not dimensions of
a participant status, so state comparison cannot see them. Derive each from the
entry's semantic type and its carried object (CEH-04-005).

An embargo register entry and a consent row each hold a status and no time of their
own. The time of a step is only in the ledger entry that recorded the step, which is
why every embargo measure has to join the two. A consent event names the register
entry it answers, because a case can hold several proposed embargoes at once and a
participant keeps one row per entry (CM-18-001, CEH-04-009).

Keep the three consent answers distinct (CEH-04-008). Inaction is recorded as
`TIMED_OUT` and never as `DECLINED` (CM-18-002), so collapsing them would make a
pocket veto indistinguishable from a refusal and destroy the pocket-veto rate as a
measure.
