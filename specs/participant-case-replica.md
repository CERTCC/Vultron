# Participant Case Replica Specification

## Overview

Requirements for how each Vultron Actor maintains and manages its local copy
(replica) of a `VulnerabilityCase`. Covers replica identity, bootstrap,
update authority, case-context message routing, reporter case discovery,
and unknown-context handling.

**Source**: `plan/IDEAS.md` IDEA-260402-02

**Cross-references**:
`specs/case-management.md` CM-01-001, CM-02-002, CM-02-010,
CM-06-001, CM-06-002;
`specs/sync-log-replication.md` SYNC-02-001, SYNC-02-003;
`specs/actor-knowledge-model.md` AKM-01-001, AKM-01-002, AKM-02-001;
`specs/response-format.md`

**Relationship to sync-log-replication.md**: This spec governs the
*participant replica lifecycle* (bootstrap, authority, routing). The SYNC
spec governs the *log replication transport* (hash-chain, per-peer state,
`Announce(CaseLogEntry)`). Both must be satisfied simultaneously; neither
supersedes the other.

---

## Replica Identity (No Stub CaseActor)

- `PCR-01-001` Each Vultron Actor MUST maintain its local case replica as an
  internal concern — there is exactly one externally-addressable Actor
  identity per participant, regardless of how many cases that Actor is
  involved in.
  - A participant MUST NOT create a separate actor identity (stub CaseActor
    clone) to manage each case copy.
  - All case-scoped protocol messages are delivered to the participant's
    single inbox and routed internally.
  - PCR-01-001 refines CM-01-001.
  - PCR-01-001 refines AKM-01-002.

- `PCR-01-002` There is exactly one CaseActor per case, operated by the
  case creator/owner.
  - The CaseActor is the sole externally-addressable entity for case-state
    operations.
  - PCR-01-002 refines CM-02-001.

## Replica Bootstrap

- `PCR-02-001` `Announce(VulnerabilityCase)` is the unified mechanism for
  delivering a full case snapshot to a participant, at every lifecycle stage.
  - An `Announce(VulnerabilityCase)` MUST carry the full inline
    `VulnerabilityCase` object (not a bare URI reference) as its `object`
    field.
  - PCR-02-001 implements AKM-03-001.
  - PCR-02-001 implements SYNC-02-001.

- `PCR-02-002` When a new participant is added to a case (whether at case
  creation or later), the CaseActor MUST send `Announce(VulnerabilityCase)`
  to that participant to deliver their initial case copy.
  - For participants added at case creation (e.g., the original reporter):
    the CaseActor sends `Announce(VulnerabilityCase)` as part of the case
    initialization sequence.
  - For participants added later (e.g., via `Invite` / `Accept`):
    the CaseActor sends `Announce(VulnerabilityCase)` as a cascade from
    the `Accept(Invite)` use case.
  - PCR-02-002 implements CM-06-001.

- `PCR-02-003` When a participant actor receives `Announce(VulnerabilityCase)`
  and has no existing local copy for that case ID, it MUST create a local
  replica from the received case object.

- `PCR-02-004` When a participant actor receives `Announce(VulnerabilityCase)`
  and already has a local replica for that case ID, it MUST apply the
  received case state as an authoritative update, subject to PCR-03-001.

- `PCR-02-005` `Create(VulnerabilityCase)` retains its semantic meaning
  ("a case was created") but MUST NOT be used as the mechanism for
  delivering a full case snapshot to participants.
  - Participant inbox handlers MUST NOT rely on `Create(VulnerabilityCase)`
    to populate or update their local case replica.
  - PCR-02-005 prevents conflation of case-creation notification with
    replica bootstrap.

## Replica Update Authority

- `PCR-03-001` A participant actor's local case replica MUST only accept
  case-state updates that originate from the CaseActor for that case.
  - The CaseActor identity is the `actor` of the `Announce(VulnerabilityCase)`
    activity or the `actor` of any `Announce(CaseLogEntry)` replication message.
  - Case-state updates attributed to any other actor (including other
    participants) MUST be rejected at the inbox handler.
  - On rejection, the handler MUST log at WARNING level, including the
    case ID, the actor ID of the unauthorized sender, and the activity ID.
  - PCR-03-001 implements CM-06-002.

- `PCR-03-002` The case owner actor MUST follow the same replica rules as
  all other participants: it MUST NOT write directly to its own local case
  copy; it MUST route all case-state changes through the CaseActor.
  - PCR-03-002 refines CM-02-010.

- `PCR-03-003` `PROD_ONLY` A participant actor MUST authenticate
  `Announce(VulnerabilityCase)` activities before accepting them as
  authoritative updates to its local replica.
  - Authentication MUST verify that the sender is the known CaseActor for
    this case using a cryptographic mechanism.

## Case Context Routing

- `PCR-04-001` The `context` field of an ActivityStreams activity is the
  canonical mechanism for routing a case-scoped message to the correct
  local case replica handler within a participant actor.
  - When a message arrives at a participant actor's inbox with a `context`
    value equal to a known local case ID, the actor MUST dispatch that
    message to the handler responsible for that case.
  - PCR-04-001 implements CM-01-002.

- `PCR-04-002` All case-scoped protocol activities sent by the CaseActor
  to participants MUST carry `context` set to the case ID.
  - All case-scoped protocol activities sent by participants to the CaseActor
    MUST also carry `context` set to the case ID.

- `PCR-04-003` The participant actor MUST be the only externally-addressable
  entity for receiving case-scoped messages on behalf of all cases it
  participates in; there MUST NOT be a separate per-case inbox.

## Reporter Case Discovery

- `PCR-05-001` Each actor's DataLayer MUST maintain a mapping from
  `VulnerabilityReport.id_` to `VulnerabilityCase.id_` for reports the
  actor has submitted.
  - This mapping allows a reporter actor to recognize that an incoming
    `Announce(VulnerabilityCase)` refers to a case bootstrapped from one
    of their prior report submissions.
  - The mapping MUST be populated when the actor creates or submits a
    `VulnerabilityReport` (via `Offer(VulnerabilityReport)`).

- `PCR-05-002` When a participant actor receives `Announce(VulnerabilityCase)`
  and the case references a report in the actor's local report-to-case map,
  the actor MUST link the local case replica to that report record.

## Unknown Case Context Handling

- `PCR-06-001` When a participant actor receives an activity whose `context`
  field does not match any known local case replica, the actor MUST NOT
  silently discard the activity.
  - The actor MUST log at WARNING level with the unknown case ID and the
    activity ID.

- `PCR-06-002` When an activity with an unknown case context arrives, the
  actor SHOULD queue the activity briefly and request a case snapshot from
  the CaseActor.
  - The request SHOULD be sent as a `Get` activity addressed to the CaseActor
    with `object` set to the unknown case ID.
  - If no `Announce(VulnerabilityCase)` response arrives within the configured
    timeout, the queued activity MUST be dropped and a WARNING logged.
  - PCR-06-002 is constrained by SYNC-03-002 (resync trigger).

- `PCR-06-003` Activities with unknown case context MUST NOT update any
  local state until a valid case replica has been established.

## Testing

- `PCR-07-001` Unit tests MUST verify that `Announce(VulnerabilityCase)` from
  the CaseActor creates a local replica when none exists.
- `PCR-07-002` Unit tests MUST verify that `Announce(VulnerabilityCase)` from
  the CaseActor updates the local replica when one exists.
- `PCR-07-003` Unit tests MUST verify that `Announce(VulnerabilityCase)` from
  an actor that is NOT the CaseActor is rejected and logged at WARNING.
- `PCR-07-004` Unit tests MUST verify that the `context` field is used to
  route incoming activities to the correct case handler.
- `PCR-07-005` Unit tests MUST verify that activities with an unknown case
  context are queued, a resync request is emitted, and the activity is dropped
  after timeout without updating any state.
- `PCR-07-006` Integration tests MUST verify the full bootstrap sequence: case
  creation → CaseActor sends `Announce(VulnerabilityCase)` → participant
  creates local replica → subsequent case-scoped activities are routed
  correctly.
- `PCR-07-007` Integration tests MUST verify the late-joiner sequence:
  `Invite` → `Accept` → CaseActor sends `Announce(VulnerabilityCase)` to new
  participant → new participant creates local replica.
