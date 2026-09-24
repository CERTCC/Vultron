---
source: CONCERN-3142
timestamp: '2026-09-17T17:21:56.600180+00:00'
title: 'SIGNATORY → DECLINED: consent withdrawal is a first-class PEC action'
type: learning
---

## Concern

Concern #3142: SIGNATORY has no legal received-side path to reject an embargo
revision (lapse-timing contested).

## Root Cause

`PEC_Trigger.DECLINE` was not valid from `SIGNATORY` in the PEC state machine.
When a `SIGNATORY` participant rejected an embargo revision proposal, the
received-side reject tree (`reject_invite_to_embargo_tree`) issued
`PEC_Trigger.DECLINE`, which raised `VultronInvalidStateTransitionError` in
`PecDimension.transition()`. The participant remained `SIGNATORY` despite
explicitly refusing.

The test `test_reject_from_signatory_is_refused_not_applied` documented this
as "current behavior, not endorsed."

A separate trigger-side gap existed: VP-13-007 and VP-13-008 require
participants to communicate their intent to comply or terminate compliance
when changing their embargo adherence, but no legal trigger-side PEC path
existed for a `SIGNATORY` to withdraw consent outside a revision cycle.

## Decision (ADR-0093)

Add `SIGNATORY → DECLINED` to the PEC transition table. Consent withdrawal
is a volitional, first-class PEC action on both the received side (participant
rejects a revision proposal) and the trigger side (participant voluntarily
terminates embargo compliance, per VP-13-007/008).

Key distinctions preserved:

- `LAPSED` = automatic; fires via `_cascade_pec_revise()` when EM enters REVISE.
  Means "you agreed to the prior terms; a revision is proposed; those prior
  terms no longer cover what is being negotiated."
- `DECLINED` = volitional; the participant explicitly said no.
- Lapse-on-propose (SIGNATORY → LAPSED when EM enters REVISE) is confirmed
  correct and is NOT changed.

The received-side reject tree requires no EM lifecycle step — a single
`DECLINE` trigger suffices once `SIGNATORY → DECLINED` is legal.

## Open Question

Whether `UNBOUND` and `DECLINED` should collapse into one "not bound" state.
Both mean the participant is not currently bound by embargo terms; they differ
only in provenance. Kept as an open question in
`docs/reference/vultron-spec/_oq-pec-unbound-declined-collapse.md` and
referenced from ADR-0093.

## Outcome

- ADR-0093 accepted: `docs/adr/0093-signatory-declined-pec-transition.md`
- CM-18-003 updated: `DECLINE` now lists `SIGNATORY` as a valid source state
- PEC transition table in `notes/participant-embargo-consent.md` updated
- Open-question admonition file created
- Docs PR: <https://github.com/CERTCC/Vultron/pull/3332>
- Implementation Task: #3333 (child of #3125, blocked-by #3142, size:M)
