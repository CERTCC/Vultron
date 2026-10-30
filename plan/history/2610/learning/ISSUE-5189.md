---
title: CM-21-021 says "active participant", which by CM-10-004 includes a closed participant that may no longer receive the Offer
type: learning
timestamp: 2026-10-26T22:30:00+00:00
source: ISSUE-5189
signal: spec-ambiguity
---

**Trigger.** A rule reuses "active participant" (CM-10-004) for a check about
sending case content or letting an actor act, and you have to decide whether a
participant at RM `CLOSED` passes.

**Question for `learn`.** CM-21-021 lets the CASE_MANAGER offer ownership only
to an "active participant", and admit the Accept only while the transferee
"is still an active participant". Under CM-10-004 and the glossary, a closed
participant stays active. But CM-23-004 says it receives no further case
content, and CM-23-018 says it may not act. The ownership Offer carries the
case inline, so sending it to a closed participant breaks CM-23-004. Should
CM-21-021 say "an active participant whose closure is not recorded", the test
`may_act_on_case` applies? Or should a closed participant be offered the case?

**Evidence.** #5189 (PR #5244) refuses a closed transferee at all three checks
(the trigger, the proposal guard and the Accept guard) through
`may_act_on_case`. The issue's list of refused kinds did not name a closed
participant, and the AC tests add it as a fifth standing. A closed transferee's
Accept was already refused by its sender check, under CM-23-018 rather than
CM-21-021.

**How to apply.** Until the requirement is settled, read "active participant" in
a send-content or may-act rule as `may_act_on_case`: active and not closed.
That is the predicate every sender guard and the case-content selection use
(`vultron/core/participants/recipients.py`).

**Promoted**: 2026-10-30 — CM-21-021 (proposal) and new CM-21-022 (Accept) refuse a
transferee that may not act on the case: active and not closed
(`specs/case-management.yaml`). Whether Active Participant should exclude Closed
Participants: Concern #5574.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5581>.
