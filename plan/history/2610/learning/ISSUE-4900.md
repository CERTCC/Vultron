---
title: "VP-03-012 and VP-02-019 say a participant sends its transitions to the other participants, but PCR-08-001 lets it address only the CASE_MANAGER"
type: learning
timestamp: "2026-10-29T17:30:00Z"
source: ISSUE-4900
signal: spec-ambiguity
---

**Trigger.** You are rendering VP-03-012 or VP-02-019 as a callout, or writing
prose about how a participant announces its own RM, EM or CS transitions.

**Claim.** VP-03-012 says a participant whose state changes "SHOULD send a
message to other Participants for each transition", and VP-02-019 says it
"SHOULD announce their RM state transitions to the other Participants". After
a case is created and the CASE_MANAGER is introduced, PCR-08-001 and
PCR-08-005 make the CASE_MANAGER the only recipient of case-scoped messages,
and PCR-08-002 calls sending to the roster a violation. The two read
consistently only if "send to other Participants" means "send to the
CASE_MANAGER, whose fan-out reaches them". Neither VP statement says so, so a
reader can take them as licensing a roster send.

**Evidence.** PR #5473 renders VP-03-012 next to PCR-08-001 in §13.2 Case
Observer capability set. Its prose names no recipient for a transition
("reports its own transitions", "the protocol recommends that it send the
message for the transition") to avoid the conflict.

**Already closed**: 2026-10-30 — tracked as #5299 AC-4, which requires VP-02-019,
VP-03-012 and VP-05-012 to route announcements through the CASE_MANAGER (verified).
Docs PR: <https://github.com/CERTCC/Vultron/pull/5581>.
