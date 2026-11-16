---
source: NOTES-case-event-history--joining-is-the-other-exception
timestamp: '2026-11-16T18:30:56.297369+00:00'
title: Joining Is the Other Exception
type: note
---

**Archived:** 2026-11-16
**Reason:** redundant — captured in CEH-04-010 and ADR-0174

---

## Joining Is the Other Exception

Joining has no state change of its own, so state comparison cannot see it, and the
entry that *first* records a participant is the wrong entry to use. The CASE_MANAGER
creates an invitee's `CaseParticipant` at `RM.RECEIVED` in its own entry while the
participant is still inert (CM-11-006), and accepting the stub Invite then *leaves*
report management at `RM.RECEIVED` (CM-11-001). So the only entry a "first records the
participant" rule can find is the one that predates joining.

Key the joining event on the **acceptance** entry instead (CEH-04-010). An inert
participant's seated state is held until then and emitted at the acceptance entry, so
a joiner's joining and report-received events share a log index; an invitee that
never accepts yields only its consent answer. That is also
what keeps a joining event off a participant that never joined: a refused invitation
and an expired one both leave the inert record untouched, so the creation entry is
there for them too. In the `rcv-reject` recording the invitee is seated, then the
invitation is rejected two entries later — a "first records" rule would report that
actor as having joined.
