---
title: "AC-4 participant-comment broadcast deferred from #1312"
type: learning
timestamp: "2026-07-22"
source: ISSUE-1312
signal: spec-ambiguity
---

ADR-0030 left the participant-comment broadcast in the review phase as an
"open design question" to be resolved at implementation time. Issue #1312
resolved it by explicitly deferring to a follow-on issue. The pipeline
functions without it because the default `ReviewAdvisoryDraft` Evaluator
is an auto-approve `AlwaysSucceed` stub (AC-3).

The interpretation made: the broadcast step (emitting an outbound Activity
and waiting for Accept/Reject responses) is out of scope for this collapse
candidate. A follow-on issue should design the review-phase protocol before
wiring the broadcast into the BT.

Impact: BT-20-004 statement notes this deferral; ADR-0030 rationale records it.
