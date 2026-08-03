---
status: accepted
date: 2026-08-03
deciders: Allen D. Householder
consulted: []
informed: []
---

# Leave(VulnerabilityCase) Is the Canonical RM Case Closure Mechanism

## Context and Problem Statement

`DEMOMA-07-001` originally stated that RM case closure MUST be driven through
`Add(ParticipantStatus, rm_state=RM.CLOSED)` sent to the Case Actor inbox —
the same path as CS transitions (fix-ready, fix-deployed, published).

PR #1909 (issue #1858) changed RM case closure to flow through
`Leave(VulnerabilityCase)` → Case Actor commits a `close_case`
`CaseLedgerEntry` → broadcast → each replica advances the leaving participant's
RM state to `RM.CLOSED` on receipt. The three CS transitions were left
unchanged.

This created a contradiction: `DEMOMA-07-001` said closure must use
`Add(ParticipantStatus)`, but the implementation used `Leave`. The question is:
which mechanism is canonical?

## Decision Drivers

- The Case Actor should be the authority for RM closure, not individual
  participants asserting their own terminal state.
- A lost `Add(ParticipantStatus, rm_state=RM.CLOSED)` message would allow a
  participant to ghost a case: their local state becomes `RM.CLOSED` but peers
  never learn about it.
- The `Leave` round-trip makes closure observable to all replicas via the
  canonical ledger rather than as a direct state assertion from the departing
  participant.
- The existing `CloseCaseReceivedUseCase` and `create_close_case_received_tree`
  already implement the `Leave` path as of #1909.

## Considered Options

- **`Leave(VulnerabilityCase)` only** — canonical closure path; `Add(ParticipantStatus,
  rm_state=RM.CLOSED)` is not a valid closure trigger.
- **`Add(ParticipantStatus, rm_state=RM.CLOSED)` only** — revert to original
  `DEMOMA-07-001` intent; roll back #1909.
- **Either path is valid** — both `Add(ParticipantStatus)` and `Leave` are
  acceptable closure triggers.

## Decision Outcome

Chosen option: **`Leave(VulnerabilityCase)` only**, because:

- It makes the Case Actor the single authority for RM closure, consistent with
  the log-centric single-writer regime (ADR-0019, ADR-0021).
- It prevents ghost-departures: a participant cannot silently reach `RM.CLOSED`
  on peers without the Case Actor having committed and broadcast a ledger entry.
- It is already implemented by #1909; rolling back would reintroduce the
  ghost-departure hazard.
- `Add(ParticipantStatus)` is semantically a status announcement, not a
  closure command; conflating the two overloads the message type.

### Consequences

- Good, because RM closure is observable on all replicas via the canonical
  ledger chain, not inferred from direct status assertions.
- Good, because the Case Actor can enforce closure sequencing (e.g., embargo
  teardown must precede closure) via the `Leave` receive path.
- Good, because `AutoCloseSequence` in `add_participant_status_tree` becomes
  correctly identified as dead code and can be removed (issue from #1910).
- Neutral, because `DEMOMA-07-001` must be amended to scope its clause to
  CS transitions only; this is a spec clarification, not a behavior change.
- Bad, because `AllParticipantsRMClosedConditionNode` (formerly step 5 of
  `add_participant_status_tree`) evaluated the all-closed condition only when
  `Add(ParticipantStatus)` arrived — which always precedes any `Leave`.
  Step 5's auto-close semantics are therefore moved to the `Leave` receive
  path (see ADR-0051, CM-23-002).

## Validation

- `CloseCaseReceivedUseCase` in `vultron/core/use_cases/received/case/lifecycle.py`
  is the implementation of the `Leave` receive path.
- `create_close_case_received_tree` in
  `vultron/core/behaviors/case/receive_close_case_tree.py` is the BT factory.
- Tests verifying RM.CLOSED is reached only after the ledger round-trip:
  `test/core/use_cases/test_leave_case_round_trip.py`.
- After #1901 lands: no `AutoCloseSequence` in `add_participant_status_tree`
  (regression test AC on the cleanup issue from #1910).

## Pros and Cons of the Options

### `Leave(VulnerabilityCase)` only

- Good, because Case Actor is the single authority for closure (ADR-0019).
- Good, because prevents ghost-departures (lost `Add(ParticipantStatus)` message).
- Good, because closure is a ledger-observable event, not a state inference.
- Neutral, because `DEMOMA-07-001` requires amendment.

### `Add(ParticipantStatus, rm_state=RM.CLOSED)` only

- Good, because consistent with DEMOMA-07-001 as originally written.
- Bad, because participant asserts its own terminal state; peers must accept it.
- Bad, because a lost message allows ghost-departure.
- Bad, because rolling back #1909 reintroduces the ghost-departure hazard.

### Either path is valid

- Good, because backward compatible.
- Bad, because two closure paths create ambiguity about which event is canonical.
- Bad, because `add_participant_status_tree` would need to handle
  `rm_state=RM.CLOSED` as a closure trigger, re-introducing the hazard.

Generated spec requirements: `case-management.yaml` CM-23-001 through CM-23-004;
`multi-actor-demo.yaml` DEMOMA-07-001 (amended).
