---
source: CONCERN-2042
timestamp: '2026-09-02T18:33:41.817575+00:00'
title: append_rm_state lacks per-session call-count guard; future participant-creation
  nodes can silently over-advance RM state
type: learning
---

## Concern

`CaseParticipant.append_rm_state()` validates each individual hop against
`is_valid_rm_transition`. What it cannot see is that a caller is stringing
together a chain of valid individual transitions (e.g. START→RECEIVED,
RECEIVED→VALID, VALID→ACCEPTED) when only one was appropriate for the
construction context.

This is exactly the bug fixed in #2017: `CreateInviteeParticipantAtAcceptedNode`
called `append_rm_state` three times, all individually valid, but the business
rule only permits one (RM.RECEIVED) at Accept(Invite) time. The fix is in place
but the structural gap remains.

## Risk

Any new BT node that creates a `VultronParticipant` and calls
`append_rm_state` multiple times will silently reproduce this class of bug.
All transitions will pass validation, no warning fires, and the participant
ends up too far along the RM ladder.

## Suggested fix

Introduce named constructors `CaseParticipant.new_at_rm(rm_state, case_id, invitee_id, roles)`
and `CaseParticipant.new_at_received(case_id, invitee_id, roles)` that call
`append_rm_state` exactly once with an adjacency guard from `RM.START`. This
encodes the CM-11-001 invariant structurally rather than in a docstring.

## Source

Surfaced during #2017 implementation (altitude review).

**Resolved**: 2026-09-02 — implementation tracked in #3072.
