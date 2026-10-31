---
title: "DEMOCI-11-013 says a step fails when its actor lacks the role, and is silent on a step whose role-granting act failed"
type: learning
timestamp: "2026-10-31T02:40:00Z"
source: ISSUE-5533
signal: spec-gap
---

**Trigger.** A scenario step's deciding role is read from the canonical case,
and the act that would have written that role into the case has already
failed — a failed `invite-actor-to-case` trigger seats no inert participant,
so the invitee holds no role to read.

**Question for `learn`.** DEMOCI-11-013's verification says the harness "fails
it if the calling actor does not hold the branch point's role". It does not say
which of two outcomes that is when the role is absent because an earlier act
failed:

1. the step raises, as a mis-declared step does, so the run's reported cause is
   the missing role; or
2. the step is a dependent step, recorded through `demo_gate` and never raised,
   so the failed act stays the reported cause (DEMOCI-01-003, EDF-06-005).

The two are not interchangeable: (1) reports a transport failure as a
declaration defect, and a reader of the demo CI log then looks at the
branch-point table instead of the delivery.

**Evidence.** The hand-placed form answered this by nesting and never had to
say so: the invitee's mark sat inside the Invite's delivery gate, so a failed
invite skipped the mark with the answer. Composing the story (#5533, PR #5588)
moved the mark into the runner, where nothing nested it, and the first
implementation raised — which a fresh-agent review caught by driving a failed
invite trigger through `run_story`. `_mark_step`
(`vultron/demo/helpers/story.py`) now takes (2) when the run has already
recorded a failure and (1) when it has not, which is the reading the nested
form had; nothing in DEMOCI-11 says it.

**The condition is coarser than the question.** `_mark_step` reads "has this
run recorded a failure", not "did the act that grants this role succeed", and
the two part company when the invite trigger commits but the delivery wait
times out: the CASE_MANAGER has already seated the inert participant, so the
role *is* readable and the mark is made, for a decision the invitee never took.
The run is red either way and the mark is only written to devlogs, so nothing
is blessed by it — but a clause that obliges outcome (2) should say whether the
mark is owed in that case, because a reader of the marks cannot otherwise tell
a decision that happened from one that could only have happened.

**How to apply.** Settle which outcome DEMOCI-11-013 obliges and say it in the
requirement, so the four remaining composition Tasks (#5534 to #5537) are not
each free to choose. Every one of them places an invitee's decision the same
way, so the same silence is reachable four more times. If (2) is the answer,
the clause also wants the condition that distinguishes it from a genuinely
mis-declared step — "a run that has recorded no failure" is the one the
implementation uses.
