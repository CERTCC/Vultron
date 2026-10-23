---
title: >-
  The EM shorthand mapping still sends EJ, ER, EA and EC to the Invite
  answer, but the owner's decision that moves EM is now a separate activity
type: learning
timestamp: "2026-10-09T18:00:00Z"
source: ISSUE-4364
signal: spec-contradiction
---

## What happened

Fixing #4364 (owner Reject of the last revision after disclosure) meant
checking which wire activity carries EJ. Two spec groups disagree.

- MSM-02-004 and MSM-02-006 say `EJ` and `ER` dispatch as
  `REJECT_INVITE_TO_EMBARGO_ON_CASE`, wire form `Reject(Invite(Event))`.
  MSM-02-005 says the same for `EC` and `ACCEPT_INVITE_TO_EMBARGO_ON_CASE`.
- MSM-07-008 and MSM-07-009 (ADR-0122) make the case owner's decision a
  separate activity, `Accept`/`Reject(EmbargoEvent, target=Case)`
  (`ACTIVATE_EMBARGO_ON_CASE`, `REJECT_EMBARGO_PROPOSAL_ON_CASE`). That
  activity is what moves EM: `REVISE → ACTIVE` for EJ, `PROPOSED → NONE`
  for ER. MSM-07-003 and MSM-07-004 say an `Accept`/`Reject(Invite)`,
  the owner's included, is only the sender's consent and moves no
  register entry.

So the formal-protocol shorthand whose effect is an EM transition maps,
in MSM-02, to a message that by MSM-07 never makes that transition.
`docs/topics/behavior_logic/use-cases/embargo-lifecycle.md` (the EJ row of
the message table) repeats the MSM-02 wire form for the owner's
rejection.

## The question for `learn`

Should MSM-02-004, MSM-02-005 and MSM-02-006 say that a shorthand's EM
effect is carried by the owner's `Accept`/`Reject(EmbargoEvent,
target=Case)`, with the Invite answer as each participant's consent? Or
should they keep the shorthands as Invite answers and state that the
EM-moving decision is a separate activity? Whichever it is, the docs
table follows it.
