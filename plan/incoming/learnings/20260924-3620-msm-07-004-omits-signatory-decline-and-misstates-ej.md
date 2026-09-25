---
title: "MSM-07-004 omits SIGNATORY → DECLINED and describes EJ as leaving EM in ACTIVE, when EJ moves REVISE → ACTIVE"
type: learning
timestamp: "2026-09-24T21:19:39Z"
source: ISSUE-3620
signal: spec-ambiguity
---

MSM-07-004 says the PEC DECLINE trigger advances a rejecting participant
"from UNBOUND, INVITED, or LAPSED to DECLINED". The §9.2 transition table in
`docs/reference/vultron-spec/_pec-state-machine.md` (line 53) also has
`Signatory --decline--> Declined`: a signatory that rejects is withdrawing
its consent. A reader who builds from MSM-07 alone would refuse that
transition.

The same requirement says that for EJ, a Reject from the case owner leaves
"EM in ACTIVE". EJ is only sent from EM *Revise*
(`docs/reference/formal_protocol/transitions.md`, sender row
`R --r--> A`), so the EM effect is REVISE → ACTIVE with the prior terms
still in force, not a no-op on ACTIVE.

I found this while writing the consent table in
`docs/topics/behavior_logic/use-cases/embargo-lifecycle.md` for PR #3680,
which follows §9.2 rather than MSM-07-004's wording. Suggested fix: add
SIGNATORY to MSM-07-004's source states, and restate the EJ clause as
"REVISE → ACTIVE".
