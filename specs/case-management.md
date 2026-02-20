# Case Management Specification

## Overview

Requirements for VulnerabilityCase lifecycle management, CaseActor responsibilities,
and the RM/EM/CS/VFD state model. Covers actor isolation at the protocol level and
the distinction between participant-specific and participant-agnostic state.

**Source**: `plan/PRIORITIES.md` (Priority 100, 200), `notes/case-state-model.md`,
`notes/bt-integration.md`, ActivityPub specification
**Cross-references**: `behavior-tree-integration.md` (BT-09, BT-10),
`handler-protocol.md` (HP-00-001, HP-00-002)

---

## Actor Isolation (MUST)

- `CM-01-001` Each actor MUST have an isolated protocol state domain
  - Actor A and Actor B MUST NOT share internal state (RM, EM, CS, BT blackboard)
  - Actors interact ONLY through ActivityStreams protocol messages via inboxes/outboxes
- `CM-01-002` Each actor's RM state MUST be maintained independently per case
  - RM state is participant-specific; each actor tracks their own RM lifecycle

## CaseActor Lifecycle (MUST)

- `CM-02-001` Each VulnerabilityCase MUST have exactly one associated CaseActor
  - CaseActor is an ActivityStreams Service object
  - CaseActor MUST be created when a VulnerabilityCase is created
- `CM-02-002` CaseActor MUST be the authoritative source of truth for case state
  - Other actors MAY maintain local copies, but the CaseActor governs the
    canonical state
- `CM-02-003` CaseActor MUST persist until the associated VulnerabilityCase is closed
- `CM-02-004` CaseActor MUST know the case owner
  - Case owner identity is stored in the VulnerabilityCase object
  - The case owner is an organizational Actor (vendor/coordinator), NOT the CaseActor
  - Initial case owner is typically the recipient of the VulnerabilityReport Offer
- `CM-02-005` `PROD_ONLY` CaseActor MUST restrict certain activities to the case owner
  - Owner-only activities include: closing the case, transferring ownership
  - See `ontology/vultron_activitystreams.ttl` (`vultron_as:CaseOwnerActivity`)
- `CM-02-006` `PROD_ONLY` CaseActor MUST enforce case-level authorization for all
  case mutations
  - **Cross-reference**: `behavior-tree-integration.md` BT-10-004

## Case State Model (MUST)

- `CM-03-001` The system MUST implement the three interacting state machines:
  RM (Report Management), EM (Embargo Management), and CS (Case State)
- `CM-03-002` RM state MUST be participant-specific
  - Each CaseParticipant carries their own RM state in `ParticipantStatus.rm_state`
  - RM state is independent per (actor × case) pair
- `CM-03-003` EM state MUST be participant-agnostic (shared per case)
  - EM state is tracked in `CaseStatus.em_state`
  - All case participants share the same EM state
- `CM-03-004` CS (PXA sub-state) MUST be participant-agnostic (shared per case)
  - PXA state is tracked in `CaseStatus.pxa_state`
  - Reflects observable world state (Public awareness, eXploit publication,
    Attack observation)
- `CM-03-005` VFD (Vendor Fix Deployment) state MUST be participant-specific
  - Only Vendors and non-vendor Deployers have a meaningful VFD state
  - Finders, Reporters, and Coordinators MUST use the null VFD state
  - VFD state is tracked in `ParticipantStatus.vfd_state`

## State Transition Correctness (MUST)

- `CM-04-001` Handlers processing RM state transitions MUST update
  `ParticipantStatus.rm_state` for the sending actor's CaseParticipant
- `CM-04-002` Handlers processing VFD state transitions MUST update
  `ParticipantStatus.vfd_state` for the sending actor's CaseParticipant
- `CM-04-003` Handlers processing EM state transitions MUST update
  `CaseStatus.em_state` — this is shared and affects all case participants
- `CM-04-004` Handlers processing PXA state transitions (public disclosure,
  exploit publication, attack observation) MUST update `CaseStatus.pxa_state`
- `CM-04-005` State transition handlers MUST NOT mix participant-specific and
  participant-agnostic state updates
  - Updating `CaseStatus.em_state` with a participant-specific value is
    incorrect and MUST be avoided

## Verification

### CM-01-001, CM-01-002 Verification

- Unit test: Actor A and Actor B maintain separate RM states for same case
- Integration test: Actor interaction only occurs via inbox/outbox message exchange
- Code review: No shared in-memory state across actor contexts

### CM-02-001, CM-02-002, CM-02-003 Verification

- Integration test: Report validation triggers VulnerabilityCase creation with
  associated CaseActor
- Unit test: CaseActor exists in DataLayer with correct case reference
- Integration test: CaseActor persists through case lifecycle; removed on case close

### CM-02-004, CM-02-005 Verification

- Unit test: CaseActor has reference to case owner
- `PROD_ONLY` Integration test: Non-owner attempt to close case → authorization error

### CM-03-001 through CM-03-005 Verification

- Unit test: RM state change updates `ParticipantStatus.rm_state`, not `CaseStatus`
- Unit test: EM state change updates `CaseStatus.em_state`, not participant status
- Unit test: PXA state change updates `CaseStatus.pxa_state`
- Code review: Vendor-only handlers check participant role before VFD state updates
- Unit test: Finder/Reporter/Coordinator participants have null VFD state

### CM-04-001 through CM-04-005 Verification

- Unit test: `engage_case` handler updates sender's `ParticipantStatus.rm_state`
- Unit test: EM state handler updates shared `CaseStatus.em_state`
- Integration test: State after two independent actors' RM transitions shows
  correct per-participant values
- Code review: No handler mixes participant-specific and agnostic state

## Related

- **Behavior Tree Integration**: `specs/behavior-tree-integration.md`
  (BT-09 actor isolation, BT-10 CaseActor creation)
- **Handler Protocol**: `specs/handler-protocol.md` (HP-00-001, HP-00-002)
- **Case State Model**: `notes/case-state-model.md` (VFD/PXA hypercube,
  participant-specific vs agnostic detail)
- **BT Integration Notes**: `notes/bt-integration.md` (actor isolation domains,
  EvaluateCasePriority directionality)
- **ActivityPub Workflows**: `docs/howto/activitypub/activities/` (workflow
  documentation for case, embargo, participant management)
- **Priorities**: `plan/PRIORITIES.md` (Priority 100: Actor independence,
  Priority 200: CaseActor as source of truth)
- **Implementation**: `vultron/as_vocab/objects/vulnerability_case.py`
- **Implementation**: `vultron/as_vocab/objects/case_status.py`
