# Vultron Semantic–AS2 Mapping Specification

## Overview

This specification defines the authoritative mapping from each Vultron semantic
message type (`MessageSemantics` enum value) to its ActivityStreams 2.0 (AS2)
wire representation. It is the single source of truth for how Vultron domain
semantics are encoded as AS2 activity structures, and is a key part of
maintaining the hexagonal architecture: core domain logic and case-state
machines depend only on `MessageSemantics` values; transport and
representation concerns (AS2 pattern matching, JSON-LD serialization, and
wire encoding) are isolated to the wire layer.

If a future transport other than AS2 is adopted, a new mapping document of this
form MUST be produced, and `vultron/wire/as2/extractor.py` MUST remain the
sole implementation location for the AS2 mapping.

**Source**: `vultron/wire/as2/extractor.py` (pattern definitions and
`SEMANTICS_ACTIVITY_PATTERNS`), `vultron/core/models/events/base.py`
(`MessageSemantics` enum), `notes/activitystreams-semantics.md`

**Notation used in this document**:

- `Verb(Object)` — an AS2 activity of type `Verb` whose `object` field is of
  type `Object`
- `Verb(Object)[field=Type]` — the activity additionally requires `field` to
  be of type `Type` (e.g., `target=VulnerabilityCase`)
- `Verb(Verb2(Object)[…])` — a nested pattern: the outer activity's `object`
  field is itself an activity matching the inner pattern; the inner pattern is
  matched against the rehydrated `object` field
- AS2 core types are rendered in `CamelCase` without a namespace prefix
  (e.g., `Note`, `Event`, `Actor`)
- Vultron domain types are prefixed implicitly by the Vultron namespace
  (e.g., `VulnerabilityReport`, `VulnerabilityCase`, `CaseParticipant`,
  `CaseStatus`, `ParticipantStatus`)

---

## General Mapping Conventions

- `VAM-01-001` Every `MessageSemantics` enum value except `UNKNOWN` MUST have
  exactly one entry in `SEMANTICS_ACTIVITY_PATTERNS` that defines its AS2
  wire representation
- `VAM-01-002` The AS2 activity patterns defined in this document MUST be
  implemented in `vultron/wire/as2/extractor.py` as `ActivityPattern` objects
  and MUST NOT be duplicated in any other module
- `VAM-01-003` Pattern entries in `SEMANTICS_ACTIVITY_PATTERNS` MUST be ordered
  from most-specific to least-specific so that `find_matching_semantics()`
  returns the correct semantic for overlapping patterns
  - Example: `VALIDATE_REPORT` (`Accept(Offer(VulnerabilityReport))`) MUST
    appear before any pattern that matches `Accept` with an unspecified object
- `VAM-01-004` An AS2 activity MUST be rehydrated (URI string references
  expanded to full objects via the DataLayer) before pattern matching; pattern
  matching MUST NOT rely on unhydrated string fields for type discrimination
- `VAM-01-005` (MUST) When a pattern specifies a nested activity as the `object` field,
  the outer activity's `object` MUST be a fully rehydrated AS2 activity object
  matching the inner `ActivityPattern`
- `VAM-01-006` Pattern matching MUST be conservative when a non-`object_` field
  is a non-rehydratable URI string: such a field MUST be treated as matching
  any expected type rather than failing the match
  - **Rationale**: Peripheral reference fields (`actor`, `target`, `context`,
    etc.) do not drive semantic dispatch; conservatively matching them avoids
    false negatives when the DataLayer cannot expand every reference
  - This conservative rule does NOT apply to the `object_` field — see
    VAM-01-009
- `VAM-01-009` (MUST) If the `object_` field of an activity remains a bare
  string URI after rehydration (i.e., the DataLayer does not have a record for
  that URI), `find_matching_semantics()` MUST return `MessageSemantics.UNKNOWN`
  - **Rationale**: Semantic dispatch depends on the object type. A bare string
    in `object_` makes the object type unknowable; proceeding as if the pattern
    matches would route the activity to the wrong handler
  - This is a stronger constraint than VAM-01-006; VAM-01-006 applies to
    non-`object_` fields only
- `VAM-01-007` `MessageSemantics.UNKNOWN` MUST be returned when no registered
  pattern matches the incoming activity
- `VAM-01-008` (MUST) Inbound activities represent state-change notifications, not
  commands; the AS2 activity type used for each semantic MUST reflect the
  completed state transition, not a requested action
  - See `notes/activitystreams-semantics.md` for the full treatment of this
    principle

---

## Report Management Messages

These messages correspond to the Report Management (RM) state machine
transitions. A `VulnerabilityReport` is the domain object at the centre of this
group.

- `VAM-02-001` `CREATE_REPORT` MUST be represented as `Create(VulnerabilityReport)`
  - Emitted when a finder first creates a vulnerability report; may be implicit
    when a report is submitted directly without a prior explicit creation step
- `VAM-02-002` `SUBMIT_REPORT` MUST be represented as `Offer(VulnerabilityReport)`
  - The `Offer` activity signals that the report is being submitted to a
    coordinator or vendor for review; this is the primary message that initiates
    the RM validation workflow
- `VAM-02-003` `ACK_REPORT` MUST be represented as `Read(Offer(VulnerabilityReport))`
  - The outer `Read` activity's `object` is the `Offer(VulnerabilityReport)`
    activity being acknowledged; signals that the receiver has read the
    submitted report without yet deciding on validity
- `VAM-02-004` `VALIDATE_REPORT` MUST be represented as
  `Accept(Offer(VulnerabilityReport))`
  - The outer `Accept` activity's `object` is the `Offer(VulnerabilityReport)`
    activity being accepted; signals that the submitted report has been
    validated as a genuine vulnerability
- `VAM-02-005` `INVALIDATE_REPORT` MUST be represented as
  `TentativeReject(Offer(VulnerabilityReport))`
  - The outer `TentativeReject` activity's `object` is the
    `Offer(VulnerabilityReport)` activity; signals a tentative negative
    determination that may be revisited
- `VAM-02-006` `CLOSE_REPORT` MUST be represented as
  `Reject(Offer(VulnerabilityReport))`
  - The outer `Reject` activity's `object` is the `Offer(VulnerabilityReport)`
    activity; signals a final negative determination that closes the report

---

## Case Management Messages

These messages correspond to lifecycle operations on a `VulnerabilityCase`.

- `VAM-03-001` `CREATE_CASE` MUST be represented as `Create(VulnerabilityCase)`
  - Emitted when an actor (typically a coordinator) creates a new case to
    track a vulnerability
- `VAM-03-002` `UPDATE_CASE` MUST be represented as `Update(VulnerabilityCase)`
  - Emitted when case metadata (title, description, identifiers, etc.) is
    modified
- `VAM-03-003` `ENGAGE_CASE` MUST be represented as `Join(VulnerabilityCase)`
  - Signals that the emitting actor has accepted the case into their active
    RM workflow (RM state → Accepted); the `object` is the case being joined
- `VAM-03-004` `DEFER_CASE` MUST be represented as `Ignore(VulnerabilityCase)`
  - Signals that the emitting actor has deferred the case (RM state →
    Deferred); the `object` is the case being deferred
- `VAM-03-005` `ADD_REPORT_TO_CASE` MUST be represented as
  `Add(VulnerabilityReport)[target=VulnerabilityCase]`
  - The `object` is the `VulnerabilityReport` being added; the `target` is
    the destination `VulnerabilityCase`
- `VAM-03-006` `CLOSE_CASE` MUST be represented as `Leave(VulnerabilityCase)`
  - Signals that the emitting actor is closing or withdrawing from the case;
    the `object` is the case being left

---

## Actor Suggestion and Invitation Messages

These messages handle adding actors to a vulnerability case, either by
suggestion (coordinators recommending other participants) or by direct
invitation.

### Actor Suggestion

- `VAM-04-001` `SUGGEST_ACTOR_TO_CASE` MUST be represented as
  `Offer(Actor)[target=VulnerabilityCase]`
  - The `object` is the suggested `Actor`; the `target` is the
    `VulnerabilityCase` to which the actor is being suggested
- `VAM-04-002` `ACCEPT_SUGGEST_ACTOR_TO_CASE` MUST be represented as
  `Accept(Offer(Actor)[target=VulnerabilityCase])`
  - The outer `Accept` activity's `object` is the
    `Offer(Actor)[target=VulnerabilityCase]` activity being accepted
- `VAM-04-003` `REJECT_SUGGEST_ACTOR_TO_CASE` MUST be represented as
  `Reject(Offer(Actor)[target=VulnerabilityCase])`
  - The outer `Reject` activity's `object` is the
    `Offer(Actor)[target=VulnerabilityCase]` activity being rejected

### Actor Invitation

- `VAM-04-004` `INVITE_ACTOR_TO_CASE` MUST be represented as
  `Invite[target=VulnerabilityCase]`
  - No specific `object` type constraint is required; the `target` is the
    `VulnerabilityCase` to which the actor is being invited; the `to`
    field addresses the invitee
- `VAM-04-005` `ACCEPT_INVITE_ACTOR_TO_CASE` MUST be represented as
  `Accept(Invite[target=VulnerabilityCase])`
  - The outer `Accept` activity's `object` is the
    `Invite[target=VulnerabilityCase]` activity being accepted
- `VAM-04-006` `REJECT_INVITE_ACTOR_TO_CASE` MUST be represented as
  `Reject(Invite[target=VulnerabilityCase])`
  - The outer `Reject` activity's `object` is the
    `Invite[target=VulnerabilityCase]` activity being rejected

### Case Ownership Transfer

- `VAM-04-007` `OFFER_CASE_OWNERSHIP_TRANSFER` MUST be represented as
  `Offer(VulnerabilityCase)`
  - Signals that the emitting actor is offering to transfer ownership of the
    case; the `object` is the `VulnerabilityCase` being transferred
  - Note: this pattern is distinct from `SUGGEST_ACTOR_TO_CASE` because the
    `target` field is absent; pattern ordering in `SEMANTICS_ACTIVITY_PATTERNS`
    MUST place `SUGGEST_ACTOR_TO_CASE` before `OFFER_CASE_OWNERSHIP_TRANSFER`
    to ensure the more-specific pattern is matched first
- `VAM-04-008` `ACCEPT_CASE_OWNERSHIP_TRANSFER` MUST be represented as
  `Accept(Offer(VulnerabilityCase))`
  - The outer `Accept` activity's `object` is the `Offer(VulnerabilityCase)`
    activity being accepted
- `VAM-04-009` `REJECT_CASE_OWNERSHIP_TRANSFER` MUST be represented as
  `Reject(Offer(VulnerabilityCase))`
  - The outer `Reject` activity's `object` is the `Offer(VulnerabilityCase)`
    activity being rejected

---

## Embargo Management Messages

These messages correspond to Embargo Management (EM) state machine transitions.
An `EmbargoEvent` (an AS2 `Event` object representing the embargo agreement) is
the domain object at the centre of this group. The `VulnerabilityCase` is
usually provided via the `context` or `target` field to associate the embargo
with a specific case.

- `VAM-05-001` `CREATE_EMBARGO_EVENT` MUST be represented as
  `Create(Event)[context=VulnerabilityCase]`
  - Emitted when a coordinator creates an embargo event; the `object` is an
    AS2 `Event` representing the proposed embargo; the `context` is the
    associated `VulnerabilityCase`
- `VAM-05-002` `ADD_EMBARGO_EVENT_TO_CASE` MUST be represented as
  `Add(Event)[target=VulnerabilityCase]`
  - The `object` is the embargo `Event`; the `target` is the
    `VulnerabilityCase` to which the embargo is being attached
- `VAM-05-003` `REMOVE_EMBARGO_EVENT_FROM_CASE` MUST be represented as
  `Remove(Event)`
  - The `object` is the embargo `Event` being removed; the `origin` field of
    the activity SHOULD identify the `VulnerabilityCase` from which it is
    removed, but is not required for pattern matching
- `VAM-05-004` `ANNOUNCE_EMBARGO_EVENT_TO_CASE` MUST be represented as
  `Announce(Event)[context=VulnerabilityCase]`
  - Signals a public (or semi-public) announcement that an embargo event is
    associated with the case; the `context` is the `VulnerabilityCase`
- `VAM-05-005` `INVITE_TO_EMBARGO_ON_CASE` MUST be represented as
  `Invite(Event)[context=VulnerabilityCase]`
  - Proposes an embargo agreement to one or more participants; the `object` is
    the embargo `Event` defining the terms; the `context` is the
    `VulnerabilityCase`; the `to` field addresses the invitee(s)
- `VAM-05-006` `ACCEPT_INVITE_TO_EMBARGO_ON_CASE` MUST be represented as
  `Accept(Invite(Event)[context=VulnerabilityCase])`
  - The outer `Accept` activity's `object` is the
    `Invite(Event)[context=VulnerabilityCase]` activity being accepted
- `VAM-05-007` `REJECT_INVITE_TO_EMBARGO_ON_CASE` MUST be represented as
  `Reject(Invite(Event)[context=VulnerabilityCase])`
  - The outer `Reject` activity's `object` is the
    `Invite(Event)[context=VulnerabilityCase]` activity being rejected

---

## Case Participant Management Messages

These messages manage the explicit creation and lifecycle of `CaseParticipant`
objects (the per-participant state records attached to a case).

- `VAM-06-001` `CREATE_CASE_PARTICIPANT` MUST be represented as
  `Create(CaseParticipant)[context=VulnerabilityCase]`
  - Emitted when a new participant record is created for a case; the `object`
    is the new `CaseParticipant`; the `context` is the `VulnerabilityCase`
- `VAM-06-002` `ADD_CASE_PARTICIPANT_TO_CASE` MUST be represented as
  `Add(CaseParticipant)[target=VulnerabilityCase]`
  - The `object` is the `CaseParticipant` being added; the `target` is the
    `VulnerabilityCase`
- `VAM-06-003` `REMOVE_CASE_PARTICIPANT_FROM_CASE` MUST be represented as
  `Remove(CaseParticipant)[target=VulnerabilityCase]`
  - The `object` is the `CaseParticipant` being removed; the `target` is
    the `VulnerabilityCase`

---

## Note Management Messages

These messages manage AS2 `Note` objects attached to a vulnerability case.

- `VAM-07-001` `CREATE_NOTE` MUST be represented as `Create(Note)`
  - Emitted when a new note is authored; the `object` is the AS2 `Note`
- `VAM-07-002` `ADD_NOTE_TO_CASE` MUST be represented as
  `Add(Note)[target=VulnerabilityCase]`
  - The `object` is the `Note` being attached; the `target` is the
    `VulnerabilityCase`
- `VAM-07-003` `REMOVE_NOTE_FROM_CASE` MUST be represented as
  `Remove(Note)[target=VulnerabilityCase]`
  - The `object` is the `Note` being detached; the `target` is the
    `VulnerabilityCase`

---

## Status Tracking Messages

These messages manage `CaseStatus` and `ParticipantStatus` objects, which
record point-in-time snapshots of the RM/EM/CS/VFD state for a case or
participant.

### Case Status

- `VAM-08-001` `CREATE_CASE_STATUS` MUST be represented as
  `Create(CaseStatus)[context=VulnerabilityCase]`
  - Emitted when a new case-status snapshot is created; the `object` is the
    `CaseStatus`; the `context` is the associated `VulnerabilityCase`
- `VAM-08-002` `ADD_CASE_STATUS_TO_CASE` MUST be represented as
  `Add(CaseStatus)[target=VulnerabilityCase]`
  - The `object` is the `CaseStatus` record; the `target` is the
    `VulnerabilityCase` whose status history is being updated

### Participant Status

- `VAM-08-003` `CREATE_PARTICIPANT_STATUS` MUST be represented as
  `Create(ParticipantStatus)`
  - Emitted when a new participant-status snapshot is created; the `object`
    is the `ParticipantStatus`
- `VAM-08-004` `ADD_PARTICIPANT_STATUS_TO_PARTICIPANT` MUST be represented as
  `Add(ParticipantStatus)[target=CaseParticipant]`
  - The `object` is the `ParticipantStatus` record; the `target` is the
    `CaseParticipant` record whose status history is being updated

---

## Unrecognized Activities

- `VAM-09-001` (MUST) An inbound AS2 activity that does not match any registered
  pattern MUST be assigned `MessageSemantics.UNKNOWN`
- `VAM-09-002` `MessageSemantics.UNKNOWN` MUST NOT have an entry in
  `SEMANTICS_ACTIVITY_PATTERNS`; the fallback is implemented by
  `find_matching_semantics()` returning `UNKNOWN` when the pattern loop
  exhausts all entries without a match

---

## Verification

### VAM-01 Verification

- Unit test: Every `MessageSemantics` value except `UNKNOWN` has an entry in
  `SEMANTICS_ACTIVITY_PATTERNS`
- Unit test: No entry for `UNKNOWN` exists in `SEMANTICS_ACTIVITY_PATTERNS`
- Unit test: Pattern ordering places more-specific nested patterns before
  less-specific ones (e.g., `VALIDATE_REPORT` before any generic `Accept`
  pattern)
- Code review: `vultron/wire/as2/extractor.py` is the only file that defines
  `ActivityPattern` instances for Vultron semantic dispatch

### VAM-02 through VAM-08 Verification

- Unit tests in `test/test_semantic_activity_patterns.py`: one test per
  semantic value confirming that a canonical example activity matches its
  expected `MessageSemantics` and does not match any other
- Unit tests in `test/test_semantic_handler_map.py`: confirm every semantic
  value maps to a registered use-case class

### VAM-09 Verification

- Unit test: An unrecognized activity (unknown verb + unknown object type)
  returns `MessageSemantics.UNKNOWN`

---

## Related

- Implementation: `vultron/wire/as2/extractor.py` — sole AS2→domain mapping
  point; defines all `ActivityPattern` objects and `SEMANTICS_ACTIVITY_PATTERNS`
- Implementation: `vultron/core/models/events/base.py` — `MessageSemantics`
  enum (authoritative domain type list)
- Implementation: `vultron/core/models/enums.py` — `VultronObjectType` enum
  (Vultron domain object type strings)
- Implementation: `vultron/wire/as2/enums.py` — `as_TransitiveActivityType`,
  `as_ObjectType` (AS2 core type strings)
- Related Spec: [semantic-extraction.md](semantic-extraction.md) — pattern
  matching algorithm, ordering rules, and rehydration requirements
- Related Spec: [architecture.md](architecture.md) — ARCH-03-001 (extractor as
  sole AS2→domain mapping point); ARCH-07-001 (wire replaceability)
- Related Spec: [response-format.md](response-format.md) — conventions for
  Accept/Reject responses to Offer/Invite activities (nested `object` field)
- Notes: [notes/activitystreams-semantics.md](../notes/activitystreams-semantics.md)
  — protocol semantics, state-change notification model, response conventions
- Vocabulary examples: `vultron/wire/as2/vocab/examples/` — canonical
  ActivityStreams activity examples used as test fixtures
