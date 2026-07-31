---
source: CONCERN-1714
timestamp: '2026-07-31T16:20:20.570831+00:00'
title: PEC NO_EMBARGO is absence, not pre-consent
type: learning
---

## Original Concern

Issue #1688 explicitly requires 'Initial PEC state sequence per participant
(NO_EMBARGO → INVITED → SIGNATORY auto-sequence at case creation)' as prologue
ledger entries. PR #1713 covers only the initial ParticipantStatus snapshot; the
three PEC state transition entries (representing the default embargo
initialization sequence) are not committed.

Scope as filed: three per-participant `event_type` entries added to prologue
backfill (PEC: NO_EMBARGO → INVITED, PEC: INVITED → SIGNATORY), as distinct
ledger entries with an appropriate `payloadSnapshot` — probably
`Add(ParticipantStatus)` entries showing intermediate states, or a new
embargo-event type.

## Why the framing was obsolete

ADR-0041 and Issue #1777 removed `WritePrologueLedgerEntriesNode` entirely; the
CaseActor now commits initialization entries natively. The requested mechanism no
longer exists. The *underlying* requirement — per-participant embargo consent
being correct and visible in the initialization ledger — was still valid, so the
concern was retargeted rather than closed as stale.

## What investigation found

The root cause sits deeper than the issue described: the PEC state machine
encodes the wrong semantics for `NO_EMBARGO`.

`participant_embargo_consent.py` documents `NO_EMBARGO` as "No embargo is in
scope for this participant" — absence of context. Its transition table treats it
as *pre-consent*: the only exit is `INVITE`, so consent is reachable only via
`NO_EMBARGO → INVITED → SIGNATORY`. That implies every consent is preceded by an
invitation, which is false for a Finder who sets the embargo on their own case
(no inviter), for participants added during case initialization (embargo already
in scope from the moment they exist, per ADR-0041), and for the reporter whose
consent is implicit in submitting the report (CM-14-005).

Three defects confirmed empirically on `main`:

1. **Invitation acceptance never records consent.** `_SignEmbargoConsentLeafNode`
   (`accept_invite_tree.py:493`) calls
   `apply_pec_trigger(PEC.NO_EMBARGO, PEC_Trigger.ACCEPT)`. The transition is
   rejected, `apply_pec_trigger` logs a warning and returns `NO_EMBARGO`
   unchanged, then the node logs "signed embargo consent for invitee" and
   returns SUCCESS. CM-10-001 silently violated. The author's mental model
   already assumed `NO_EMBARGO → SIGNATORY` was legal.

2. **Consent never reaches the ledger snapshot.** Three sites assign
   `participant.embargo_consent_state = PEC.SIGNATORY` directly
   (`case_proposal_received_tree.py:873`, `nodes/embargo.py:433`,
   `nodes/participant/participant_add.py:389`). The plain Pydantic write skips
   `_sync_latest_status_metadata()`, so the emitted snapshot carries the
   self-contradictory pair `{"embargoAdherence": true, "emConsentState":
   "NO_EMBARGO"}`.

3. **CM-14-005 unimplemented.** `_AddReporterParticipantNode:513` hardcodes
   `em_consent_state=PEC.NO_EMBARGO`; no later node seeds the reporter.

The machinery to prevent (2) already existed and was simply unused:
`ParticipantStatus.consent` is a `PecDimension` (ADR-0036) whose `transition()`
is fail-closed.

## Transferable lessons

- **A state machine's docstring and its transition table can disagree, and the
  table can be the wrong one.** The docstring definition of `NO_EMBARGO` was
  correct; the table encoded a different concept. When a state's prose says
  "absence of X" but its only exit transition implies "awaiting X", suspect a
  conflation.
- **Code that calls a transition and ignores the result is evidence about
  intent.** `apply_pec_trigger(NO_EMBARGO, ACCEPT)` in
  `accept_invite_tree.py` was a prior author asserting the transition *should*
  exist. A no-op call plus a success log is a strong signal the FSM is wrong,
  not the caller.
- **Warn-and-return-unchanged helpers produce silent protocol violations.**
  `apply_pec_trigger` logs and returns the input state on an invalid trigger
  instead of raising, so every caller that ignores the return value reports
  success while recording nothing. This is the same fail-open shape flagged for
  `CreateParticipantStatusNode` in ISSUE-1825.
- **Fixing the semantics can dissolve the implementation risk rather than add
  to it.** The initial plan (per-transition ledger entries) would have shifted
  every downstream `log_index` — the exact failure that got PR #1746 reverted.
  Correcting `NO_EMBARGO` semantics made consent reachable in one transition, so
  initialization still commits one entry per participant and the revert risk
  vanished. Worth checking whether a "risky" plan is downstream of a modelling
  error before engineering around the risk.
- **Scalar mirror fields desync from their dimension objects.** Where both
  `CaseParticipant.embargo_consent_state` (scalar) and
  `ParticipantStatus.consent` (`PecDimension`) hold the same fact, writing the
  scalar does not update the dimension, and it is the dimension that gets
  serialized into the ledger.

## Resolution

**Resolved**: 2026-07-31 — reframed from prologue back-fill to native-init PEC
correctness; implementation tracked in #1865, #1866, #1867, #1868.

Docs PR: <https://github.com/CERTCC/Vultron/pull/1864>
ADR: `docs/adr/0048-pec-no-embargo-is-absence-not-pre-consent.md`
Spec: `specs/case-management.yaml` CM-18-001, CM-18-003, CM-18-005, CM-18-006,
CM-18-007 (version 1.1.0 → 1.2.0)
Notes: `notes/participant-embargo-consent.md`, `notes/case-ledger-authority.md`
