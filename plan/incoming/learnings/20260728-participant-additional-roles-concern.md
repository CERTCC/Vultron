---
title: No protocol mechanism for participant to request additional roles after joining
type: learning
timestamp: 2026-07-28
source: ISSUE-1745
signal: concern
---

Surfaced during ISSUE-1745 bugfix: once a participant joins via the suggest-actor
flow, there is no protocol path to request additional CVD roles. The fix
intentionally restricts role assignment to what was offered — the acceptor cannot
add roles. This is correct security behavior, but it leaves a legitimate use-case
unaddressed.

Filed as Concern #1752. See that issue for details and a sketch of a possible
`Request(CaseParticipant)` activity type reusing the ADR-0026 Accept/Reject
pattern.
