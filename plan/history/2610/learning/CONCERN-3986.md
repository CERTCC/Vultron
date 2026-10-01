---
source: CONCERN-3986
timestamp: '2026-10-01T14:12:04.391255+00:00'
title: A repeated CaseProposal after the embargo exited re-runs creation-time initialization
type: learning
---

## Observation

`CaseEmbargoAlreadyInitializedNode` (#3393) makes `InitializeDefaultEmbargoNode` idempotent by reading "initialized" as "the case has an `active_embargo` attached" — the same evidence `AdvanceEMStateToActiveNode` and `AttachEmbargoToCaseNode` use to skip their own step. That closes the duplicate-revision defect the report-with-embargo demo found, but only narrows a pre-existing exposure: a repeated `Create(CaseProposal)` for a report whose case has since moved to `EM.EXITED` (embargo terminated, `active_embargo` cleared) falls through both guard arms and runs the creation arm, which mints and activates a fresh creation-time embargo on a case whose embargo was deliberately ended.

Reaching it needs a same-report proposal to arrive after termination. With the vendor no longer re-proposing an answered report (#3393) that is now a retry-of-a-lost-proposal or a hostile sender, so the window is narrow, but the outcome — an embargo re-imposed by a duplicate — is the kind of silent state change the refusal-arm rules exist to prevent.

## Question to decide

What does "creation-time initialization already ran" mean once the embargo is gone? Candidates: any EM history on the case (`current_status.em.state != EM.NONE`, which would have to be read through `ReadEmStateNode` per the AC-1 rule); a durable per-case marker written by the creation arm; or treating the whole native-initialization block as reachable only from `CreateCaseFromProposalNode`, never from `LoadExistingCaseNode` (the AC-1/AC-2 reuse path), which is the structural fix and would also retire the per-node idempotency guards.

## Where it is recorded today

- `vultron/core/behaviors/case/nodes/embargo_resolution.py` (`CaseEmbargoAlreadyInitializedNode` docstring)
- `notes/embargo-default-semantics.md` § "Initialization runs once per case"
- Related: #3977 (what the CaseActor answers a same-report duplicate with)

Governing specs: EP-04-002, EP-04-008, CP-05-006, EMB-13, BT-17-001

Surfaced in the pre-PR review of #3393.

**Resolved**: 2026-10-01 — implementation tracked in #4019.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4018>.
Spec: `specs/embargo-policy.yaml` (new EP-04-012).
Notes: `notes/embargo-default-semantics.md`, `notes/case-proposal.md`.

**Outcome.** The scenario is narrower than written: the EM machine has no
transition out of `EXITED`, so the creation arm stores an orphan `EmbargoEvent`
and then fails rather than activating a fresh embargo — an orphan write and a
proposal never answered. Decided: the guard reads the EM state through
`ReadEmStateNode` and treats anything other than `NONE` as "already
initialized" (the active-embargo reference was a strict subset of that
evidence). The structural alternative — initialization reachable only from the
fresh-case branch — was rejected because the reuse branch is also how a
redelivery finishes a half-built case. Recorded alongside: "duplicate" in the
reuse path means an exact redelivery of the same proposal, not a second report
about the same vulnerability; the report-keyed `LoadExistingCaseNode` and
CBT-06-002 (a second recipient gets its own case) are handed to #3977.
