---
source: CONCERN-3009
timestamp: '2026-09-03T16:18:39.835669+00:00'
title: replica-apply path must enforce composite-state entailments
type: learning
---

## Concern

`ApplyParticipantStatusFromLedgerNode` (replica-apply path) enforced only the
RM monotonic ratchet (RSH-05-007). It did not call `cross_machine_violations()`
/ `composite_state_violations()` to check RM↔VF, RM↔D, and VF↔D entailments.
A buggy or hostile CaseActor could write an impossible composite state into the
canonical hash chain, and every replica would silently adopt it.

## Resolution

RSH-05-021 added to `specs/received-status-handling.yaml`: when
`ApplyParticipantStatusFromLedgerNode` encounters an entry whose effective
state violates composite-state entailments, the tree MUST NOT apply the status
and MUST emit `Create(ProcessingFault)` with failure class
`StatusAssertionRefused/ImpossibleState` to the CaseActor (guaranteed by tree
structure via Selector fallback, not node-level side-effect).

ADR-0061 updated to remove the ISSUE-3009 open-gap note and reflect that the
replica-apply path now enforces both the RM ratchet (RSH-05-007) and the
composite-state fault (RSH-05-021).

## Key decisions

- **`Create(ProcessingFault)` not `Reject(CaseLedgerEntry)`**: Reject causes
  replay loops; ProcessingFault notifies the CaseActor of a content violation
  without requesting retransmission.
- **Tree-structural guarantee**: the fault emission is a Selector fallback
  (`Selector(Apply, EmitFaultThenFail)`), so either SUCCESS (apply) or fault +
  FAILURE is guaranteed by tree structure, not node internals.
- **Error hierarchy**: new fault class
  `VULTRON_FAILURE_STATUS_ASSERTION_REFUSED_IMPOSSIBLE_STATE` is a URI sub-path
  of `VULTRON_FAILURE_STATUS_ASSERTION_REFUSED`, making it a recognisable
  narrowing of the same fault family.
- **Rename**: `cross_machine_violations` → `composite_state_violations` and
  module `cross_machine_invariants.py` → `composite_state_invariants.py` to
  eliminate ambiguity between "state machine" and "computing machine/server".

## Implementation issue

# 3113 — blocked by #3009 (docs PR #3112 must merge first)

Docs PR: <https://github.com/CERTCC/Vultron/pull/3112>
