---
title: "Received-Side Status Authorization: Two-Gate Design"
status: active
kind: guidance
description: >
  How a CASE_MANAGER turns an inbound status claim into case state: the
  one-move-one-mover pipeline (ADR-0108), the two independent gates for
  adoption and embargo teardown (ADR-0046), whole accept or reject of a
  received status (ADR-0107), and CaseStatus emission authority.
related_specs:
  - specs/behavior-tree-node-design.yaml
  - specs/received-status-handling.yaml
  - specs/case-ledger-processing.yaml
  - specs/behavior-tree-integration.yaml
  - specs/cs-behavior.yaml
  - specs/embargo-policy.yaml
  - specs/em-behavior.yaml
  - specs/sync-ledger-replication.yaml
  - specs/protocol-asks.yaml
related_notes:
  - notes/embargo-lifecycle.md
  - notes/bt-integration.md
  - notes/call-out-configuration.md
  - notes/message-type-reference.md
  - notes/bt-pitfalls.md
  - notes/case-communication-model.md
  - notes/case-joining.md
  - notes/protocol-asks.md
  - notes/case-state-model.md
relevant_packages:
  - vultron/core/behaviors/status
  - vultron/core/behaviors/report
  - vultron/core/behaviors/sync
  - vultron/core/use_cases/received
---

# Received-Side Status Authorization: Two-Gate Design

The tree shapes are in the module docstrings of
`vultron/core/behaviors/status/add_participant_status_tree.py` and
`add_case_status_tree.py`; this note keeps the rules that are easy to break.

## One move, one mover: the pipeline is the authority (ADR-0108)

A participant-state move arrives in two layers: the **act** (an activity such as
`Accept(Offer(Report))`, `Join(Case)` or `Accept(Invite(EmbargoEvent))`) and the
**declaration** (`Add(ParticipantStatus)` / `Add(CaseStatus)`). Both are
expected, and neither is "the" authoritative form (RSH-08-002). Authority is a
property of the pipeline:

- **Only the CASE_MANAGER turns an announcement into case state.** It applies the
  state machine's acceptance rule to the *sender's* declaration, whichever
  message carried it (RSH-06-006, RSH-08-001). A participant declares in
  `Add(ParticipantStatus)`; `Add(CaseStatus)` is the CASE_MANAGER's own
  (RSH-04-005). Every other participant applies the ledger (PCR-03-001,
  RSH-08-003).
- **One RM acceptance rule, from one place.** The activity-typed RM handlers and
  `CheckParticipantStatusAcceptableNode` share `classify_rm_declaration`
  (`core/states/rm.py`), composed by `report/rm_declaration_tree.py`. Tests on
  both paths run one table, `test/support/rm_declaration.py`. Do not give a new
  RM handler its own adjacency check.
- **Received-side state writes are CASE_MANAGER-gated** (`manager_effects`); a
  replica stores the activity and converges on the `Announce(CaseLedgerEntry)`
  fan-out. `test/architecture/test_received_tree_state_writes_are_gated.py`
  enforces it, and every committed semantic type must be replayed
  (`test/architecture/test_ledger_semantic_types_are_replayed.py`).
- **Add the replay node before gating the effect.** Gating a state-writing
  effect whose semantic type no replica replays blinds every replica (RSH-08-004
  before RSH-08-003).
- **The one exception** is a signatory whose ledger stream is paused: the
  CASE_MANAGER's direct `Remove(EmbargoEvent)` or `Announce(EmbargoEvent)` is its
  only channel, so it applies its own teardown (through the one apply
  function, ADR-0124) or revision (through `EmbargoLifecycle`), gated on
  `AwaitsEmbargoEndingNoticeNode` (CM-31-010).

## Two independent gates (ADR-0046)

A CASE_MANAGER receiving `Add(ParticipantStatus)` answers two separate
questions, each behind its own seam:

1. **Adoption** — `StatusAdoptionGate`: is the sender's claimed `CaseStatus`
   canonical for the case? A Fallback whose first child,
   `SenderIsCaseOwnerNode`, is a hard bypass: the CASE_OWNER's updates are
   authoritative by definition, so asking them to approve their own update would
   be circular.
2. **Side-effects** — `EmbargoTeardownAuthorizationGate`: may embargo teardown
   run? It runs after the canonical write, inside a `FailureIsSuccess` wrapper so
   a blocked teardown still leaves the tree `SUCCESS`.

On the adoption path the gates run in one tree, in order, with no inbox
round-trip (RSH-01-003, RSH-01-004). `add_case_status_tree` runs the teardown
gate only.

**Both seams are call-outs that require Case Owner approval by default**
(RSH-07-001, RSH-07-002, ADR-0076). A permissive backend
(`STATUS_AUTHORIZATION_PERMISSIVE` in
`vultron/core/behaviors/call_out/bundles/status_authorization.py`) MAY be
configured for trusted or demo deployments, but MUST be explicit (RSH-07-003)
and MUST NOT be used to route around a gate that is refusing (RSH-07-005).

**Do not complete `RequireCaseOwnerApprovalNode`.** It is a deny-always stub
because an Evaluator asked "is this approved?" at the moment approval is first
needed can only ever answer *no*. RSH-07-004 (ADR-0080) replaces it with a
conversation-state routing subtree that reads authorization from the ledger and
asks the owner when none is recorded; see [protocol-asks.md](protocol-asks.md).
Tracked by #2885.

**Threat monitoring is event-driven.** A sentinel actor (or any informed
participant) posts `Add(ParticipantStatus)` carrying the P/X/A change; the
CASE_MANAGER's received tree decides whether to adopt it. The simulation
`MonitorThreats` nodes are fuzzer stubs for the sentinel's internal logic and
are not wired into the received pipeline (see
`docs/developer/reference/bt-fuzzer/rm-threat.md`).

## Whole accept or reject (RSH-09, ADR-0107)

`CheckParticipantStatusAcceptableNode` accepts a received `ParticipantStatus` as
sent or refuses all of it; `CheckCaseStatusAcceptableNode` does the same for
`CaseStatus`. Rules:

- **Never record a status nobody sent.** No guard rewrites the received status
  and no node patches the ledger snapshot: the ledger records what was asserted
  and every replica copies it (RSH-09-001, CLP-07-013, CM-23-016).
- **An omitted dimension is absent, not refused.** A status with no `vf`, `d`
  or `caseStatus` is recorded without them; filling them from the receiver's
  own state would record a value the sender never sent (ADR-0075). Judge each
  dimension against its most recent recorded value, not the latest status's,
  or an omission resets the baseline and a later regression passes
  (`RecordedBaseline`, RSH-09-003). `rm` is never omitted: a status without
  `rmState` states `START`.
- **Report every reason.** The refusal notice names each refused dimension and
  why, so the sender fixes the update in one round trip (RSH-09-002,
  EH-07-001).
- **The guards are read-only and run before the commit** (CLP-10-006,
  CLP-10-009). A refused regression still owes the RSH-06-004 note: the guard
  publishes the anomaly before it fails, and the note runs as a
  `refusal_effects` (CLP-10-022).
- **`em` is never judged from a participant status.** EM is derived from the
  embargo register; a received `CaseStatus` whose EM differs from
  `case.em_state` is refused (RSH-09-005, ADR-0122).
- **Emit, receive and replica-apply share one entailment evaluator**,
  `composite_state_violations()` in
  `vultron/core/states/composite_state_invariants.py`, evaluated on the status
  as received (RSH-09-004). No path calls an individual `violation_*` function.
- **RM↔VF and RM↔D are sound, not complete.** `RM_STATES_CONSISTENT_WITH_FIX`
  approximates "passed `RM.ACCEPTED`" with the states reachable from it, so a
  peer that accepts and reports a ready fix in one message is accepted.
  Tightening it needs RM history (ISSUE-3015).

## Embargo teardown on P, X or A

`ThreatTerminationBranchNode` fires `terminate_embargo_bt` when the canonical
`CaseStatus` carries CS.P, CS.X or CS.A (RSH-03-001 to RSH-03-003). It does no
sender check: authorization happened at the gates.

- **A CASE_MANAGER-declared status is torn down by the CASE_MANAGER.** At any
  other actor the branch does nothing (`_DeclaredByCaseManagerNode`, RSH-03-004);
  the replica waits for the committed teardown entry. The skip decides *who*
  tears down, not *whether*.
- **A blocked teardown leaves the PXA↔EM entailment violated** (CSB-18-002 to
  CSB-18-004). `PxaEmInvariantDiagnosticNode` detects it after the cascade, at
  the CASE_MANAGER only, and commits a note as its own `add_note_to_case`
  entry, so a lagging replica never reports the gap (RSH-06-004, #4829).

## CaseStatus emission authority (RSH-04)

- **Only the CASE_MANAGER emits `Add(CaseStatus)`.** Other participants embed a
  suggested `CaseStatus` in `Add(ParticipantStatus)` and let the gates decide
  (RSH-04-001).
- **Refuse `Add(CaseStatus)` from anyone else.** `add_case_status_tree` has no
  adoption gate, so admitting it from a participant skips the Case Owner's
  approval (RSH-04-005, RSH-07-001).
- **Every CASE_MANAGER-side EM or P/X/A mutation is followed by a canonical
  `CaseStatus` ledger write** through `EmitCaseStatusUpdateNode` (RSH-04-002,
  RSH-04-003); without it every replica stays stale. Wire it after any new EM
  lifecycle node.
- **Adoption passes the report to the snapshot.** On the participant path the
  case has not moved when `EmitCaseStatusUpdateNode` runs, so a bare snapshot
  re-commits the old P/X/A. Pass `reported_status_id`; the node adopts the
  report's P/X/A unless it regresses the case's (RSH-01-003, RSH-09-005, #4956).
- **Write directly, never through the inbox.** The CASE_MANAGER records its own
  state change by an inner commit, not by sending `Add(CaseStatus)` to itself
  (RSH-04-004, ADR-0108). The inbox gates exist for *external* suggestions.
