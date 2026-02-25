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
- `CM-02-007` `VulnerabilityCase` MUST include a `notes: list[as_NoteRef]`
  field to record case-scoped notes created via `AddNoteToCase` activities
  - Provides a canonical link from a case to in-scope notes, consistent with
    `case_participants` and `vulnerability_reports` tracking
  - Handlers implementing `AddNoteToCase` MUST append the `as_NoteRef` to
    `VulnerabilityCase.notes`
- `CM-02-008` When a `VulnerabilityCase` is created from an originating
  `VulnerabilityReport` Offer, the vendor (case recipient / owner) MUST be
  recorded as the initial primary participant
  - `VulnerabilityCase.attributed_to` MUST be set to the vendor/coordinator's
    actor ID at case creation
  - Handlers creating a case SHOULD create a `VendorParticipant` before
    appending other participants (e.g., finder)

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
- `CM-03-006` Collection fields that hold status histories MUST be pluralized
  and documented as history collections
  - `VulnerabilityCase` MUST expose `case_statuses: list[CaseStatusRef]`
    (history); a read-only property `case_status` MAY return the most recent
    `CaseStatus` by timestamp
  - `CaseParticipant` MUST expose `participant_statuses: list[ParticipantStatus]`
    (history); a read-only property `participant_status` MAY return the current
    `ParticipantStatus`
  - Handlers MUST append new status objects to the pluralized history lists;
    handlers MUST NOT mutate historical items in-place
  - The read-only property MUST be computed (not direct assignment)

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

## Object Model Relationships (MUST)

- `CM-05-001` The system MUST distinguish the following domain objects as
  separate, non-interchangeable types:
  - `VulnerabilityReport`: an inbound report describing one or more
    potential vulnerabilities; submitted by a finder or reporter
  - `VulnerabilityCase`: a coordination unit grouping one or more reports
    and tracking state across participants
  - `VulnerabilityRecord`: a persistent identifier record for a confirmed
    vulnerability (e.g., CVE number); created during coordination
  - `Publication`: a public disclosure artifact linked to a case; may
    reference external URLs rather than storing content
- `CM-05-002` A `VulnerabilityCase` MUST reference at least one
  `VulnerabilityReport`; a case with zero reports MUST NOT exist
- `CM-05-003` A `VulnerabilityCase` SHOULD reference at least one
  `VulnerabilityRecord` before closure; cases with no associated record at
  closure SHOULD log a warning
- `CM-05-004` A `VulnerabilityCase` MAY have zero or more associated
  publications
- `CM-05-005` Publications associated with a case MUST be stored as
  reference links (metadata including title, publisher, date, URL) rather
  than embedding full publication content
  - Exception: a case MAY embed a publication snapshot as a
    `VulnerabilityCase` note when content preservation is explicitly required
- `CM-05-006` One report MAY describe multiple vulnerabilities; one case MAY
  group multiple reports (e.g., when overlapping participants are involved)
- `CM-05-007` Multiple publications MAY arise from a single case
  (e.g., coordinated simultaneous disclosure by multiple vendors)

## Case Update Broadcast (MUST)

- `CM-06-001` When the CaseActor updates canonical case state, it MUST
  notify all current case participants
  - Notification MUST be sent as an ActivityStreams activity to each
    participant's inbox
- `CM-06-002` Participants receiving a case update notification MUST treat
  the update as authoritative only when it originates from the CaseActor
  - **Cross-reference**: CM-02-002
- `CM-06-003` `PROD_ONLY` Case update notifications MUST include the
  updated CaseActor URL so participants can fetch the current case state
  if needed
- `CM-06-004` `PROD_ONLY` Participants MUST authenticate case update
  notifications before accepting them as authoritative
  - **Cross-reference**: `prototype-shortcuts.md` PROTO-01-001

## CVD Action Rules API (SHOULD)

- `CM-07-001` The system SHOULD expose an endpoint that returns the set of
  valid actions available to a case participant given the current case state
  and their role
  - This supports both human and agent consumers in knowing which protocol
    actions are applicable at any given moment
  - **Cross-reference**: `agentic-readiness.md` AR-07-001, AR-07-002
- `CM-07-002` The action rules response MUST include the participant's role
  and the current RM, EM, CS, and VFD states relevant to that participant
- `CM-07-003` The action rules response MUST list valid next actions as
  structured objects including the action name and any required parameters

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

### CM-05-001 through CM-05-007 Verification

- Unit test: `VulnerabilityCase`, `VulnerabilityReport`, `VulnerabilityRecord`,
  and `Publication` are separate Pydantic model types
- Unit test: Creating a case with no reports raises a validation error
- Unit test: Publication stored as reference link includes title, publisher,
  date, and URL fields

### CM-06-001 through CM-06-004 Verification

- Unit test: After a case state update, CaseActor outbox contains one
  notification per active case participant
- Code review: Participant inboxes are populated from `CaseParticipant` list
  at notification time

### CM-07-001 through CM-07-003 Verification

- Integration test: `GET /actors/{case_actor_id}/action-rules?participant={id}`
  returns structured action list for known participant
- Unit test: Action rules reflect current RM/EM/CS state for the participant

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
- **Agentic Readiness**: `specs/agentic-readiness.md` (AR-07-001, AR-07-002)
- **Object IDs**: `specs/object-ids.md`
- **Do Work Behaviors**: `notes/do-work-behaviors.md`
- **Implementation**: `vultron/as_vocab/objects/vulnerability_case.py`
- **Implementation**: `vultron/as_vocab/objects/case_status.py`
