---
source: CONCERN-5653
timestamp: '2026-11-03T17:25:30.800625+00:00'
title: EMB-17 did not cover a late Accept of an open embargo proposal
type: learning
---

## Summary

EMB-17 named three answers to a late `Accept(Invite(EmbargoEvent))`: honour it
when it names the Active Embargo (EMB-17-002), re-invite the accepter to the
Active Embargo when it names another one (EMB-17-003), and do nothing when the
case has no Active Embargo and no Proposed Embargo (EM `EXITED` or `NONE`,
EMB-17-004). A case in EM `PROPOSED` fits none of them: it has an open proposal
but no Active Embargo.

## Surface Symptom vs. Underlying Problem

- Surface symptom: the wording of EMB-17 said "current embargo", which read as
  covering the `PROPOSED` case. #5645 reworded it to Active Embargo, as the code
  reads it, and the gap became visible.
- Underlying problem: no requirement said what the CASE_MANAGER does when an
  invitee whose `INVITED` row for an open proposal timed out then accepts that
  proposal late. The invitation-expiry sweep times out rows for open proposals as
  well as for the embargo in force (CM-28-015), so the case can happen.
- Correct and kept: the three existing arms, and the rule that a late Accept is
  never refused on deadline grounds (EMB-17-001, ADR-0065).

## Category

Spec gap (protocol behaviour unspecified for one EM state).

## Severity

Medium. A willing participant's answer was lost with only a WARNING, which goes
against the intent of ADR-0065.

## Evidence

- `vultron/core/behaviors/embargo/nodes/late_accept.py` `late_accept_route`: EM
  `PROPOSED` routes to `REINVITE`.
- `vultron/core/behaviors/embargo/nodes/reinvite.py`
  `ReinviteLateAccepterNode._invite_owed`: with no `active_embargo_id` it sends
  nothing and logs a WARNING ("no embargo in force to re-invite"), and because the
  arm is a diversion the Accept is not recorded.
- `specs/em-behavior.yaml` EMB-17-003's precondition (the case has an Active
  Embargo) and EMB-17-004 (EM `EXITED` or `NONE`) between them left out
  `PROPOSED`.
- `test/core/behaviors/embargo/nodes/test_late_accept.py`
  `test_no_embargo_in_force_sends_nothing` pinned the silent drop, citing
  EMB-17-007, which governs the EXITED/NONE case instead.

## What the planning decided

MSM-07-003 already settled the protocol question: an `Accept(Invite(EmbargoEvent))`
is always its sender's own consent, and the embargo it names "may be the active
embargo, a first proposal (EM PROPOSED) or a proposed revision". The Accept tree's
own `IsAnswerableEmbargoNode` guard already enforces that line. EMB-17 was the
outlier: it narrowed "answerable" to "the Active Embargo", and the code followed
the narrow version.

So the route keys on whether the case can still answer the named embargo — its
`ACTIVE` register entry or an open proposal — and the re-invite names the Active
Embargo, or the earliest-expiring open proposal when none is in force (EP-08-002).
The no-op arm is unchanged; it already read "no Active Embargo **and** no Proposed
Embargo". No decision record was warranted: this corrects a spec statement to
match decisions ADR-0122 and ADR-0152 already carry.

**Resolved**: 2026-11-03 — implementation tracked in #5732.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5731>.
Spec: `specs/em-behavior.yaml`.
Notes: `notes/embargo-lifecycle.md`, `notes/participant-embargo-consent.md`.
