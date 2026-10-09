---
source: CONCERN-3863
timestamp: '2026-09-30T14:05:23.663735+00:00'
title: Decide whether the CASE_MANAGER announces the creation-time embargo revision
  to peers (EP-04-003 shortest-wins loser)
type: learning
---

## Summary

Issue #3392 (PR #3850) implements EP-04-003's shortest-wins at case creation: when the Reporter's proposed embargo and the case owner's actor default both apply, the shorter becomes `EM.ACTIVE` and the longer is registered as a pending revision through `EmbargoLifecycle.propose_embargo`, leaving the case at `EM.REVISE`.

Two consequences were recorded in the PR body and `notes/embargo-default-semantics.md` as open design points rather than decided:

1. **The pending revision is registered locally only.** No `Invite(EmbargoEvent)` is emitted to peers, so the party whose longer terms lost never learns that its proposal is pending as a revision, and nothing drives a re-accept round. EP-04-003 asks only for the registration ("the longer SHOULD be registered as a pending revision"); it is silent on announcement.
2. **REVISE with two SIGNATORY participants who never saw the revision.** `RegisterLongerProposalAsRevisionNode` runs inside `InitializeDefaultEmbargoNode`, *before* the case-proposal tree seeds the vendor and the reporter as SIGNATORY (CM-14-005 seeds consent to the *active* embargo). The alternative ordering would lapse everyone with no node driving a re-accept.

## Question to decide

Should the CASE_MANAGER announce the creation-time revision to the case's participants as an `Invite(EmbargoEvent)` (so the normal EV/EC/EJ negotiation runs and PEC states are re-derived), or is a locally registered revision the intended end state until a participant proposes something?

If announcement is the answer, this issue covers: an emit node after the revision registration (recipient set = case participants, sender = CASE_MANAGER per CM-24), the participants' receive-side handling of a revision they did not propose, and an EP-04-003 amendment naming the announcement.

## Governing specs

EP-04-003, EP-04-004, CM-14-005, CM-24, EMB-18-001, ADR-0096 (amended in #3850).

## Where it is recorded today

- `notes/embargo-default-semantics.md`, section on the sender-proposal seam.
- PR #3850 body, "Two design points recorded rather than changed".

**Resolved**: 2026-09-30 — implementation tracked in #3916 (blocked by #3913). Decision recorded as ADR-0113 (embargo revision negotiation relays through the CASE_MANAGER; the ledger carries state but never asks), planned as a bundle with Concerns #3892 and #3836.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3912>.
Spec: `specs/embargo-policy.yaml` (EP-09, EP-04-011, EP-08-004); `specs/em-behavior.yaml` (EMB-03 description).
Notes: `notes/embargo-default-semantics.md`.
