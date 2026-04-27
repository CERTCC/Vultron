# Case Management Specification

## Overview

Requirements for VulnerabilityCase lifecycle management, CaseActor responsibilities,
and the RM/EM/CS/VFD state model. Covers actor isolation at the protocol level and
the distinction between participant-specific and participant-agnostic state.

**Source**: `plan/PRIORITIES.md` (Priority 100, 200), `notes/case-state-model.md`,
`notes/bt-integration.md`, ActivityPub specification
**Cross-references**: `behavior-tree-integration.md` (BT-09, BT-10),
`handler-protocol.md` (HP-00-001, HP-00-002),
`actor-knowledge-model.md` (AKM-01-001, AKM-01-002)

---

## Actor Isolation

- `CM-01-001` Each actor MUST have an isolated protocol state domain
  - Actor A and Actor B MUST NOT share internal state (RM, EM, CS, BT blackboard)
  - Actors interact ONLY through ActivityStreams protocol messages via inboxes/outboxes
  - This constraint applies regardless of physical deployment topology; actors that
    are co-located on the same server MUST still interact via the wire protocol and
    MUST NOT communicate via direct DataLayer access or in-process calls bypassing
    the inbox/outbox API
- `CM-01-002` Each actor's RM state MUST be maintained independently per case
  - RM state is participant-specific; each actor tracks their own RM lifecycle

## CaseActor Lifecycle

- `CM-02-001` Each VulnerabilityCase MUST have exactly one associated CaseActor
  - CaseActor is an ActivityStreams Service object
  - CaseActor MUST be created when a VulnerabilityCase is created
- `CM-02-002` CaseActor MUST be the authoritative source of truth for case state
  - Other actors MAY maintain local copies, but the CaseActor governs the
    canonical state
- `CM-02-003` CaseActor MUST persist until the associated VulnerabilityCase is closed
- `CM-02-004` CaseActor MUST know the case owner
  - Case owner identity is stored in the VulnerabilityCase object using the
    `case_owner` field (wire vocabulary: `vultron:caseOwner`)
  - The case owner is an organizational Actor (vendor/coordinator), NOT the CaseActor
  - Initial case owner is typically the recipient of the VulnerabilityReport Offer
  - `VulnerabilityCase.case_owner` MUST be set at case creation and updated
    only via ownership-transfer activities (see `OFFER_CASE_OWNERSHIP_TRANSFER`)
  - The `vultron:caseOwner` wire property MUST carry the full actor URI of
    the current case owner; it MUST NOT be a local identifier
- `CM-02-005` `PROD_ONLY` CaseActor MUST restrict certain activities to the case owner
  - Owner-only activities include: closing the case, transferring ownership
  - See `ontology/vultron_activitystreams.ttl` (`vultron_as:CaseOwnerActivity`)
- `CM-02-006` `PROD_ONLY` CaseActor MUST enforce case-level authorization for all
  case mutations
  - CM-02-006 is-implemented-by BT-10-004
- `CM-02-007` `VulnerabilityCase` MUST include a `notes: list[as_NoteRef]`
  field to record case-scoped notes created via `AddNoteToCase` activities
  - Provides a canonical link from a case to in-scope notes, consistent with
    `case_participants` and `vulnerability_reports` tracking
  - Handlers implementing `AddNoteToCase` MUST append the `as_NoteRef` to
    `VulnerabilityCase.notes`
- `CM-02-008` (MUST) When a `VulnerabilityCase` is created from an originating
  `VulnerabilityReport` Offer, the vendor (case recipient / owner) MUST be
  recorded as the initial primary participant
  - `VulnerabilityCase.attributed_to` MUST be set to the vendor/coordinator's
    actor ID at case creation
  - Handlers creating a case SHOULD create a `VendorParticipant` before
    appending other participants (e.g., finder)
- `CM-02-009` The CaseActor MUST apply its own trusted timestamp to every
  state-changing event it receives, regardless of any timestamp supplied by
  the sending participant
  - This applies to all state-changing messages: participant join/leave,
    embargo proposals and acceptances, notes added, status updates, and any
    other activity that modifies canonical case state
  - Participant-supplied timestamps MUST NOT be used as authoritative
    timestamps for case history
  - **Rationale**: The CaseActor's clock is the only trusted source of time
    for event ordering within a case; using participant-supplied timestamps
    would allow different copies of a case (held by different actors) to
    disagree on event order, undermining auditability and the
    single-source-of-truth guarantee
  - CM-02-009 depends-on CM-02-002
- `CM-02-010` The CaseActor and the case owner (named actor) MUST have distinct
  actor identities — each with their own actor ID — even when co-located on the
  same server
  - A named actor MUST NOT serve as its own CaseActor; the two roles MUST remain
    separate protocol identities
  - **Rationale**: Enforcing distinct identities ensures that all case-state
    transitions pass through the wire protocol regardless of deployment topology,
    preserving audit integrity and enabling future separation onto independent
    containers without protocol changes
  - CM-02-010 refines CM-01-001
  - CM-02-010 depends-on CM-02-001

## Case State Model

- `CM-03-001` The system MUST implement the three interacting state machines:
  RM (Report Management), EM (Embargo Management), and CS (Case State)
  - CM-03-001 implements VP-01-001
  - CM-03-001 implements VP-13-001
  - CM-03-001 implements VP-14-001
- `CM-03-002` RM state MUST be participant-specific
  - Each CaseParticipant carries their own RM state in `ParticipantStatus.rm_state`
  - RM state is independent per (actor × case) pair
  - CM-03-002 implements VP-01-002
  - CM-03-002 implements VP-02-002
  - CM-03-002 implements VP-03-001
- `CM-03-003` A shared EM state MUST be tracked at the case level in
  `CaseStatus.em_state` to represent the collective embargo agreement
  - CM-03-003 implements VP-04-002
  - CM-03-003 implements VP-13-009
  - CM-03-003 implements VP-14-001
- `CM-03-008` Each `CaseParticipant` MUST track their own embargo consent state
  via the `ParticipantStatus.embargo_adherence` field
  - `embargo_adherence: bool = True` is a derived property of the participant's
    position in a 5-state consent machine (see `notes/participant-embargo-consent.md`)
  - `embargo_adherence` is `True` iff the participant is in the `SIGNATORY`
    consent state; all other states yield `False`
  - The 5 consent states are: `NO_EMBARGO`, `INVITED`, `SIGNATORY`, `LAPSED`,
    `DECLINED` (see notes for full transition table and timer-based pocket-veto
    transitions from `INVITED` and `LAPSED` to `DECLINED`)
  - The shared `CaseStatus.em_state` represents the collective embargo
    agreement; per-participant `embargo_adherence` tracks each actor's
    individual consent to the current embargo terms
  - CM-03-008 implements VP-04-002
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
- `CM-03-007` RM state transitions MUST use the established protocol activity
  types without introducing new activity types for reverse transitions
  - Re-engagement from `DEFERRED` back to `ACCEPTED` MUST use the same `Join`
    activity type as initial engagement (`RmEngageCase`), not an `Undo` activity
  - Using `Undo` for re-engagement MUST NOT be implemented; `Undo` implies
    retracting a prior state assertion, not a new forward state transition
  - **Rationale**: Keeps the RM symbol set minimal and produces clean audit
    histories; `Undo` conflates historical negation with a new forward
    transition
  - CM-03-007 implements VP-02-004

## State Transition Correctness

- `CM-04-001` Handlers processing RM state transitions MUST update
  `ParticipantStatus.rm_state` for the sending actor's CaseParticipant
  - CM-04-001 implements VP-02-002
  - CM-04-001 implements VP-02-003
  - CM-04-001 implements VP-03-001
  - CM-04-001 implements VP-13-005
- `CM-04-002` Handlers processing VFD state transitions MUST update
  `ParticipantStatus.vfd_state` for the sending actor's CaseParticipant
- `CM-04-003` Handlers processing EM state transitions MUST update the
  appropriate EM state field based on who is accepting and the current state:
  - When the **case owner** (identified by `VulnerabilityCase.attributed_to`)
    accepts an embargo proposal, the shared `CaseStatus.em_state` MUST
    transition to `ACTIVE`; the case owner's `ParticipantStatus.embargo_adherence`
    MUST also transition to `SIGNATORY` state (yielding `embargo_adherence=True`)
  - When a **non-owner participant** accepts an embargo proposal, only that
    participant's `ParticipantStatus.embargo_adherence` MUST transition to
    `SIGNATORY`; the shared `CaseStatus.em_state` MUST NOT be changed if it
    is already `ACTIVE`
  - When the shared `CaseStatus.em_state` is already `ACTIVE` and a non-owner
    calls accept-embargo, the handler MUST succeed idempotently (HTTP 2xx),
    updating only that participant's consent state; a 4xx error MUST NOT be
    returned in this case
  - When the shared `CaseStatus.em_state` enters `REVISE`, all participants'
    consent states MUST transition from `SIGNATORY` to `LAPSED`
  - CM-04-003 implements VP-06-001
  - CM-04-003 implements VP-09-001
  - CM-04-003 implements VP-11-001
  - CM-04-003 implements VP-11-002
  - CM-04-003 implements VP-14-001
  - CM-04-003 implements VP-14-002
  - CM-04-003 depends-on CM-03-008
- `CM-04-004` (MUST) Handlers processing PXA state transitions (public disclosure,
  exploit publication, attack observation) MUST update `CaseStatus.pxa_state`
  - CM-04-004 implements VP-03-002
  - CM-04-004 implements VP-14-003
  - CM-04-004 implements VP-14-004
- `CM-04-005` Handlers that implement VFD or PXA transitions MUST validate
  the requested transition against the authoritative current state before
  persisting it
  - Applies to future fix-readiness, deployment, public-disclosure, exploit,
    and attack-observation flows
  - The validation rule MUST be shared across code paths that persist the
    corresponding state so invalid sequences are rejected consistently
- `CM-04-006` State transition handlers MUST NOT mix participant-specific and
  participant-agnostic state updates incorrectly
  - The shared `CaseStatus.em_state` MUST NOT be transitioned by non-owner
    participant accept-embargo actions; only the case owner's acceptance
    drives the shared EM state
  - Participant-specific EM consent MUST be tracked via
    `ParticipantStatus.embargo_adherence` (and its underlying 5-state consent
    machine), NOT via `CaseStatus.em_state`
  - CM-04-006 implements VP-13-009
  - CM-04-006 depends-on CM-03-008

## Object Model Relationships

- `CM-05-001` The system MUST distinguish the following domain objects as
  separate, non-interchangeable types:
  - `VulnerabilityReport`: an inbound report describing one or more
    potential vulnerabilities; submitted by a finder or reporter
  - `VulnerabilityCase`: a coordination unit grouping one or more reports
    and tracking state across participants
  - `VulnerabilityRecord`: a persistent identifier record for a confirmed
    vulnerability; may carry one or more identifiers from different
    namespaces (e.g., CVE ID, CERT/CC VU#, vendor-specific ID)
  - `CaseReference`: a typed external reference associated with a case
    (e.g., public advisory, patch, vendor bulletin, or other
    vulnerability-related resource); links to external resources rather
    than embedding their content
- `CM-05-002` A `VulnerabilityCase` MUST reference at least one
  `VulnerabilityReport`; a case with zero reports MUST NOT exist
  - CM-05-002 implements VP-02-015
  - CM-05-002 implements VP-02-020
- `CM-05-003` A `VulnerabilityCase` SHOULD reference at least one
  `VulnerabilityRecord` before closure; cases with no associated record at
  closure SHOULD log a warning
- `CM-05-004` A `VulnerabilityCase` MAY have zero or more associated
  `CaseReference` objects
- `CM-05-005` `CaseReference` objects MUST include at minimum a `url` field;
  SHOULD include a `name` field (human-readable title); MAY include a `tags`
  field (array of one or more type descriptors, e.g., `"patch"`,
  `"vendor-advisory"`, `"third-party-advisory"`, `"exploit"`,
  `"release-notes"`)
  - The `url`, `name`, and `tags` structure aligns with the CVE JSON schema
    reference format
    (<https://github.com/CVEProject/cve-schema>)
  - Exception: a case MAY embed a reference snapshot as a
    `VulnerabilityCase` note when content preservation is explicitly required
- `CM-05-006` One report MAY describe multiple vulnerabilities; one case MAY
  group multiple reports (e.g., when overlapping participants are involved)
- `CM-05-007` Multiple `CaseReference` objects MAY arise from a single case
  (e.g., coordinated simultaneous disclosure by multiple vendors)
- `CM-05-008` `VulnerabilityRecord` identifiers MUST be treated as opaque
  strings; the system MUST NOT restrict identifier values to CVE ID format
  or any other specific namespace
  - **Rationale**: Different organizations use different identifier namespaces
    (CVE, CERT/CC VU#, vendor-assigned IDs, etc.); requiring a specific
    format excludes valid records and prevents multi-namespace support
- `CM-05-009` A `VulnerabilityRecord` SHOULD support a list of alias
  identifiers from different namespaces for the same vulnerability
  - **Rationale**: Multiple IDs from different namespaces may refer to the
    same underlying vulnerability (e.g., a CVE ID and a CERT/CC VU# ID)
- `CM-05-010` (MUST) When a `VulnerabilityRecord` is a `CVERecord` (i.e., it
  carries a CVE ID), its data MUST conform to the CVE JSON schema
  (<https://github.com/CVEProject/cve-schema>)
  - The `CVERecord` Pydantic model SHOULD reuse the CVE JSON schema
    `reference` definition for its `references` array, ensuring
    compatibility with CVE data interchange formats

## Case Update Broadcast

- `CM-06-001` When the CaseActor updates canonical case state, it MUST
  notify all current case participants
  - Notification MUST be sent as an ActivityStreams activity to each
    participant's inbox
  - CM-06-001 implements VP-02-019
  - CM-06-001 implements VP-03-012
  - CM-06-001 implements VP-08-001
- `CM-06-002` Participants receiving a case update notification MUST treat
  the update as authoritative only when it originates from the CaseActor
  - CM-06-002 depends-on CM-02-002
- `CM-06-003` `PROD_ONLY` Case update notifications MUST include the
  updated CaseActor URL so participants can fetch the current case state
  if needed
- `CM-06-004` `PROD_ONLY` Participants MUST authenticate case update
  notifications before accepting them as authoritative
  - CM-06-004 is-constrained-by PROTO-01-001
- `CM-06-005` When a note is added to a case, the CaseActor MUST
  broadcast the note to all case participants (excluding the note
  author)
  - Recipients MUST be derived from
    `VulnerabilityCase.actor_participant_index`
  - CM-06-005 depends-on OX-03-001
  - CM-06-005 depends-on CM-02-001

## CVD Action Rules API

- `CM-07-001` The system SHOULD expose an endpoint that returns the set of
  valid actions available to a case participant given the current case state
  and their role
  - This supports both human and agent consumers in knowing which protocol
    actions are applicable at any given moment
  - Endpoint:
    `GET /actors/{actor_id}/cases/{case_id}/action-rules`
  - The actor/case pair MUST resolve internally to the matching
    `CaseParticipant`; callers MUST NOT be required to supply both actor ID and
    participant ID
  - CM-07-001 refines AR-07-001
  - CM-07-001 refines AR-07-002
- `CM-07-002` The action rules response MUST include the participant's role
  and the current RM, EM, CS, and VFD states relevant to that participant
- `CM-07-003` The action rules response MUST list valid next actions as
  structured objects including the action name and any required parameters

## Verification

### CM-01-001, CM-01-002 Verification

- Unit test: Actor A and Actor B maintain separate RM states for same case
- Integration test: Actor interaction only occurs via inbox/outbox message exchange
- Code review: No shared in-memory state across actor contexts
- Code review: Named actors and case actors never share a DataLayer instance
  or bypass the inbox endpoint to exchange state

### CM-02-001, CM-02-002, CM-02-003 Verification

- Integration test: Report validation triggers VulnerabilityCase creation with
  associated CaseActor
- Unit test: CaseActor exists in DataLayer with correct case reference
- Integration test: CaseActor persists through case lifecycle; removed on case close

### CM-02-004, CM-02-005 Verification

- Unit test: CaseActor has reference to case owner
- Unit test: `VulnerabilityCase.case_owner` is set at case creation and holds the
  full actor URI of the owning named actor
- Code review: Case-owner field is serialized using `vultron:caseOwner` vocabulary
  term in ActivityStreams wire format
- `PROD_ONLY` Integration test: Non-owner attempt to close case → authorization error

### CM-02-009 Verification

- Unit test: Participant join event stored with CaseActor-applied timestamp,
  not sender-supplied time
- Unit test: Embargo acceptance event stored with CaseActor-applied timestamp
- Unit test: Note-added event stored with CaseActor-applied timestamp
- Code review: All case state mutation handlers apply CaseActor timestamp,
  not activity-supplied timestamp

### CM-02-010 Verification

- Unit test: CaseActor actor ID differs from the owning named actor's actor ID
- Integration test: Two co-located actors exchange state only via inbox/outbox
  messages, not via shared DataLayer access
- Code review: No code path allows a named actor to act as its own CaseActor

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

### CM-05-001 through CM-05-010 Verification

- Unit test: `VulnerabilityCase`, `VulnerabilityReport`, `VulnerabilityRecord`,
  and `CaseReference` are separate Pydantic model types
- Unit test: Creating a case with no reports raises a validation error
- Unit test: `CaseReference` model requires a `url` field; `name` and `tags`
  are optional
- Unit test: `VulnerabilityRecord` accepts any non-empty string as identifier
- Unit test: `VulnerabilityRecord.aliases` field stores a list of string IDs
- Unit test: `CVERecord` model validates data against CVE JSON schema structure

### CM-06-001 through CM-06-004 Verification

- Unit test: After a case state update, CaseActor outbox contains one
  notification per active case participant
- Code review: Participant inboxes are populated from `CaseParticipant` list
  at notification time

### CM-07-001 through CM-07-003 Verification

- Integration test:
  `GET /actors/{actor_id}/cases/{case_id}/action-rules`
  returns structured action list for the matching participant in the selected
  case
- Unit test: Action rules reflect current RM/EM/CS state for the participant

## Domain Model Architecture

- `CM-08-001` The system SHOULD maintain a clear separation between the wire
  representation, domain model, and persistence model for CVD objects
  - **Wire representation**: ActivityStreams JSON exchanged between participants
    at the inbox/outbox boundary
  - **Domain model**: Internal objects with business logic, explicit invariants,
    and append-only event history semantics
  - **Persistence model**: Storage-optimized structures for the DataLayer
  - These three concerns SHOULD be independently evolvable; wire format changes
    SHOULD NOT require domain logic changes, and vice versa
- `CM-08-002` Domain objects MUST NOT directly inherit from
  ActivityStreams base types; explicit `from_core()` / `to_core()` translation
  methods MUST be provided at the wire boundary (see `specs/architecture.yaml`
  ARCH-12-001 through ARCH-12-007 and `notes/domain-model-separation.md`)
  - **Current state**: Domain objects (`VulnerabilityCase`, `VultronReport`,
    `VultronCaseLogEntry`, etc.) are already pure Pydantic `BaseModel` —
    they do NOT inherit from AS2 types. The remaining work is establishing
    the formal `from_core()`/`to_core()` contract on all wire types.

## Redacted Case View

- `CM-09-001` `PROD_ONLY` The system SHOULD support a `RedactedVulnerabilityCase`
  type for sharing case information with invited-but-not-yet-accepted participants
  - A `redact(invitee_id)` method on `VulnerabilityCase` SHOULD return a
    `RedactedVulnerabilityCase` containing only the fields appropriate for
    an invitee: severity indication, general vulnerability type, and proposed
    embargo terms
  - Full report content, case discussion history, prior participant details,
    and reporter-identifying information MUST NOT be included
- `CM-09-002` `PROD_ONLY` The ID of a `RedactedVulnerabilityCase` MUST be
  cryptographically unrelated to the full `VulnerabilityCase` ID
  - **Rationale**: Prevents an attacker who obtains a redacted case ID from
    inferring the full case ID
- `CM-09-003` `PROD_ONLY` Each invitee MUST receive a distinct
  `RedactedVulnerabilityCase` ID
  - **Rationale**: Prevents cross-correlation of redacted IDs to infer
    participant list size or identities
- `CM-09-004` For the prototype, the `Invite` activity MAY reference the case
  by full case ID only, deferring the redacted view to a later phase
  - CM-09-004 is-constrained-by PROTO-01-001

## Per-Participant Embargo Acceptance

- `CM-10-001` `CaseParticipant` MUST track which embargo(es) a participant has
  explicitly accepted
  - A participant added to a case MUST be on record as having accepted the
    active embargo at the time they joined
  - CM-10-001 implements VP-05-001
- `CM-10-002` Embargo acceptances MUST be timestamped by the CaseActor at
  the time of receipt, not using the participant's claimed timestamp
  - **Rationale**: The CaseActor applies the only trusted timestamp; the
    participant's reported time cannot be verified
  - CM-10-002 depends-on CM-02-002
  - CM-10-002 implements CM-02-009
- `CM-10-003` The `CaseParticipant` model SHOULD include an
  `accepted_embargo_ids: list[str]` field recording the IDs of
  `EmbargoEvent` objects the participant has explicitly accepted
  - An `Accept(Invite(Actor, Case))` is an implicit acceptance of the
    current active embargo at join time
  - An `Accept(Offer(Embargo))` is an explicit acceptance of a specific embargo
- `CM-10-004` Before sharing case updates with a participant, the system MUST
  verify that the participant has accepted the current active embargo
  - If not, the system MUST send a new `Offer(Embargo)` before continuing

### CM-09-001 through CM-09-004 Verification

- `PROD_ONLY` Unit test: `VulnerabilityCase.redact(invitee_id)` returns a
  `RedactedVulnerabilityCase` excluding report content, discussion, and
  participant details
- `PROD_ONLY` Unit test: Two calls to `redact()` with different invitee IDs
  return objects with distinct IDs
- `PROD_ONLY` Unit test: Redacted case ID shares no substrings with the full
  case ID

### CM-10-001 through CM-10-004 Verification

- Unit test: Newly added `CaseParticipant` has the current active embargo ID
  in `accepted_embargo_ids`
- Unit test: Embargo acceptance timestamp is set by CaseActor clock, not
  participant-supplied time
- Integration test: Case update sent to a participant who has not accepted the
  current embargo triggers `Offer(Embargo)` first

## CM-11 Invitation Acceptance Lifecycle

When an actor accepts an invitation to join a case, the system MUST
complete a set of cascading effects automatically, without requiring
additional triggers from the demo-runner or external caller.

- `CM-11-001` When an actor accepts a case invitation, the accepting
  actor's RM state MUST advance to ACCEPTED
  - This means `AcceptInviteActorToCaseReceivedUseCase` (or its BT
    equivalent) MUST invoke `SvcEngageCaseUseCase` internally after
    creating the participant record
  - CM-11-001 implements VP-03-012
  - CM-11-001 depends-on CM-03-001
- `CM-11-002` After auto-engagement (CM-11-001), the accepting actor
  SHOULD emit an `RmEngageCaseActivity` to notify the case owner
  - This activity is queued to the accepting actor's outbox for
    delivery to the case-actor inbox
  - CM-11-002 depends-on OX-02-001

### CM-11-001, CM-11-002 Verification

- Unit test: Accepting an invitation triggers RM state advance to
  ACCEPTED without a separate `engage-case` trigger
- Unit test: `RmEngageCaseActivity` is emitted to the outbox after
  auto-engagement
- Integration test: Demo-runner triggers only `accept-invite`; system
  automatically engages the actor and notifies the case owner

## CM-12 Case Creation Timing

Cases MUST be created at report receipt so that case-level tracking begins
immediately. The term "proto-case" is **redefined** in this context: a
proto-case is a case object that exists but has not yet been validated
(RM state is RM.RECEIVED or RM.INVALID). See ADR-0015 for rationale.

- `CM-12-001` (MUST) A `VulnerabilityCase` MUST be created when an
  `Offer(Report)` activity is received by the vendor actor
  - This MUST occur in `SubmitReportReceivedUseCase`, at RM.RECEIVED
  - Case creation MUST NOT be deferred to report validation (RM.VALID)
  - CM-12-001 implements ADR-0015
  - CM-12-001 supersedes any prior requirement to create cases at RM.VALID
- `CM-12-002` (MUST) At case creation, the system MUST create two initial
  `VultronParticipant` records:
  - The reporter (finder): `rm_state=RM.ACCEPTED` (they created and
    submitted the report)
  - The receiver (vendor): `rm_state=RM.RECEIVED` (they have received the
    report and not yet validated it)
  - CM-12-002 depends-on CM-03-001
  - CM-12-002 depends-on CM-02-008
- `CM-12-003` (MUST) When a case is created from an `Offer(Report)`, the
  case owner MUST queue a `Create(Case)` activity to notify the reporter
  that a case has been opened
  - This activity MUST be queued to the case owner's outbox at case
    creation time
  - CM-12-003 depends-on OX-02-001
- `CM-12-004` (SHOULD) A default embargo SHOULD be initialized at case
  creation (RM.RECEIVED)
  - CM-12-004 refines DUR-07-002 (which now applies at case receipt)
  - When applied, the resulting `CaseStatus.em_state` MUST be `EM.ACTIVE`,
    not `EM.PROPOSED` — see `specs/embargo-policy.yaml` EP-04-001
  - If no embargo is initialized at receipt, one MUST exist before the
    case transitions to RM.VALID (see DUR-07-004)
- `CM-12-005` (MUST) `InvalidateReportReceivedUseCase`,
  `CloseReportReceivedUseCase`, and `ValidateReportReceivedUseCase` MUST
  dereference the incoming report ID to the associated case ID before
  delegating to the corresponding case-level use case
  - This ensures report-centric protocol activities can locate and update
    the case created at receipt
  - CM-12-005 depends-on CM-12-001

### CM-12 Verification

- Unit test: `SubmitReportReceivedUseCase` creates a `VulnerabilityCase`
  immediately upon receiving `Offer(Report)`
- Unit test: Two `VultronParticipant` records are created at case creation
  (reporter at RM.ACCEPTED, receiver at RM.RECEIVED)
- Unit test: A `Create(Case)` activity is queued to the outbox at case
  creation
- Unit test: `ValidateReportReceivedUseCase` does NOT create a case
  (case already exists from CM-12-001)
- Unit test: `InvalidateReportReceivedUseCase` dereferences report→case
  and delegates to `InvalidateCaseUseCase`
- Unit test: A default embargo exists on the case before RM.VALID
  transition

## Related

- **Behavior Tree Integration**: `specs/behavior-tree-integration.yaml`
  (BT-09 actor isolation, BT-10 CaseActor creation)
- **Handler Protocol**: `specs/handler-protocol.yaml` (HP-00-001, HP-00-002)
- **Case State Model**: `notes/case-state-model.md` (VFD/PXA hypercube,
  participant-specific vs agnostic detail)
- **Domain Model Separation**: `notes/domain-model-separation.md` (wire/domain/
  persistence architecture and migration guidance)
- **BT Integration Notes**: `notes/bt-integration.md` (actor isolation domains,
  EvaluateCasePriority directionality)
- **Triggerable Behaviors Notes**: `notes/triggerable-behaviors.md`
  (Invitation-Ready Case Object, Per-Participant Embargo Acceptance Tracking)
- **ActivityPub Workflows**: `docs/howto/activitypub/activities/` (workflow
  documentation for case, embargo, participant management)
- **Priorities**: `plan/PRIORITIES.md` (Priority 100: Actor independence,
  Priority 200: CaseActor as source of truth)
- **Agentic Readiness**: `specs/agentic-readiness.yaml` (AR-07-001, AR-07-002)
- **Object IDs**: `specs/object-ids.yaml`
- **Do Work Behaviors**: `notes/do-work-behaviors.md`
- **Protocol Event Cascades**: `notes/protocol-event-cascades.md`
  (cascading automation design principle, identified gaps in BT
  automation and activity addressing)
- **Encryption**: `specs/encryption.yaml`
- **Implementation**: `vultron/wire/as2/vocab/objects/vulnerability_case.py`
- **Implementation**: `vultron/wire/as2/vocab/objects/case_status.py`
