---
status: accepted
date: 2026-08-03
deciders: Allen D. Householder
consulted: []
informed: []
---

# CaseActor Has Its Own RM Lifecycle Tracked via CaseParticipant

## Context and Problem Statement

The CaseActor registers itself as a `CaseParticipant` with
`CVDRole.COORDINATOR + CVDRole.CASE_MANAGER` during case initialization
(ADR-0041, CM-22-001). However, this `CaseParticipant` record has historically
had no `ParticipantStatus` entries and therefore no RM state.

With `Leave(VulnerabilityCase)` as the canonical RM closure path (ADR-0050),
owner `Leave` must advance the Case Actor's own RM state to `RM.CLOSED` as
the penultimate step before emitting the final `case_fully_closed`
`CaseLedgerEntry` (CM-23-002). This requires the Case Actor to have a valid
RM lifecycle starting from `RM.RECEIVED`.

The question is: should the Case Actor have an RM lifecycle at all, and if so,
what do the RM states mean for a coordinator?

## Decision Drivers

- Owner `Leave` processing (CM-23-002) requires the Case Actor to advance to
  `RM.CLOSED`; this requires a prior RM state to transition from.
- Uniform RM lifecycle tracking across all participants, including the
  coordinator, keeps the case-level RM model consistent and avoids
  special-casing the Case Actor in ledger consumers.
- Each RM transition should be a `CaseLedgerEntry` (CM-02-009) so the
  Case Actor's role in case initialization is part of the traceable ledger
  history.
- The RM state machine transitions are already meaningful for the coordinator
  if the states are reinterpreted in terms of case-level events rather than
  report-validation events.

## Considered Options

- **Case Actor has full RM lifecycle** — add `ParticipantStatus` entries at
  `RM.RECEIVED`, `RM.VALID`, `RM.ACCEPTED` during bootstrap; advance to
  `RM.CLOSED` on owner Leave. Each is a `CaseLedgerEntry`.
- **Bootstrap directly at RM.ACCEPTED** — skip `RECEIVED`/`VALID`; start at
  `ACCEPTED`. Simpler but bypasses the state machine.
- **No RM lifecycle for Case Actor** — Case Actor's `CaseParticipant` never
  has `RM` state; case closure is a distinct mechanism that does not involve
  the RM machine.

## Decision Outcome

Chosen option: **Case Actor has full RM lifecycle**, because:

- It avoids introducing a `START → ACCEPTED` shortcut that would break the
  RM state machine invariants for all participants.
- The RM transitions map cleanly to case-level events for the coordinator
  (see CM-23-006 for the mapping).
- Each transition as a `CaseLedgerEntry` gives the ledger a complete
  protocol-significant history of case initialization.
- Owner `Leave` can then cleanly advance the Case Actor to `RM.CLOSED` as
  the penultimate ledger step.

### Consequences

- Good, because case initialization is fully traceable in the ledger with
  timestamped CaseActor RM transitions.
- Good, because `RM.CLOSED` for the Case Actor is a clean terminal signal
  that the case is fully closed.
- Good, because ledger consumers need no special-casing for the Case Actor
  participant.
- Neutral, because `AllParticipantsRMClosedConditionNode` currently skips
  `CVDRole.CASE_MANAGER` participants. After the sidecar impl issue lands,
  this skip can be removed so the Case Actor's `RM.CLOSED` participates in
  the all-closed check.
- Bad, because `RegisterCaseActorAsParticipantNode` in
  `case_proposal_received_tree.py` must be updated to emit three
  `ParticipantStatus` records at bootstrap instead of none.
- Bad, because three new `CaseLedgerEntry` records are emitted per case
  initialization (minor overhead; acceptable for audit completeness).

## Case Actor RM State Meanings

The RM state machine labels map to the following case-level events for the
Case Actor:

| RM State | Meaning for Case Actor |
|---|---|
| `RM.RECEIVED` | A `CaseProposal` has been received and is being evaluated |
| `RM.VALID` | The `CaseProposal` is correctly formatted and actionable; case creation has begun |
| `RM.ACCEPTED` | The `VulnerabilityCase` has been successfully created and is being coordinated |
| `RM.CLOSED` | The Case Owner has sent `Leave(VulnerabilityCase)`; the case is fully closed |

`RM.DEFERRED` and `RM.INVALID` are not used in the Case Actor's lifecycle
(a `CaseProposal` that is not valid is rejected, not deferred).

## Validation

- `RegisterCaseActorAsParticipantNode` (or equivalent) in
  `case_proposal_received_tree.py` must emit `ParticipantStatus` records for
  `RM.RECEIVED`, `RM.VALID`, and `RM.ACCEPTED` at bootstrap.
- Each bootstrap transition must produce a `CaseLedgerEntry` in the canonical
  ledger.
- Owner `Leave` processing must advance the Case Actor participant to
  `RM.CLOSED` before emitting the final `case_fully_closed` entry.
- `AllParticipantsRMClosedConditionNode` currently skips `CASE_MANAGER`;
  after the sidecar impl issue lands, this skip SHOULD be removed.
- Implementation tracked in the sidecar issue from #1910 planning.

Generated spec requirements: `case-management.yaml` CM-23-005 through CM-23-007.
