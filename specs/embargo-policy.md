# Embargo Policy Specification

## Overview

Requirements for a standardized embargo policy record associated with an
Actor profile. Allows actors to declare their default embargo preferences
so that coordinators can evaluate compatibility before proposing an embargo
or inviting an actor to a case.

**Source**: `notes/do-work-behaviors.md` ("Reporting Behavior as Central
Coordination", "Prior Art and References (Embargo Policy)")
**Cross-references**: `case-management.md`, `response-format.md`,
`agentic-readiness.md`, `duration.md` (duration string format)

---

## Policy Record Format

- `EP-01-001` An Actor profile MAY include a `embargo_policy` field
  containing a structured embargo policy record
- `EP-01-002` The embargo policy record MUST include the following fields:
  - `actor_id`: URI of the Actor to which the policy applies
  - `inbox`: URL of the Actor's ActivityPub inbox
  - `preferred_duration`: ISO 8601 duration string representing the Actor's
    preferred embargo duration (e.g., `"P90D"` for ninety days)
  - EP-01-002 implements VP-05-001
  - EP-01-002 implements VP-07-001
  - EP-01-002 implements VP-07-002
  - EP-01-002 depends-on DUR-01-001 (ISO 8601 duration format)
- `EP-01-003` The embargo policy record SHOULD include the following fields:
  - `minimum_duration`: minimum acceptable embargo duration as ISO 8601
    duration string; the Actor SHOULD reject embargoes shorter than this value
  - `maximum_duration`: maximum acceptable embargo duration as ISO 8601
    duration string; the Actor SHOULD reject embargoes longer than this value
  - `notes`: free-text description of the Actor's embargo preferences (e.g.,
    "prefer 45 days but consider shorter for critical vulnerabilities")
  - EP-01-003 implements VP-05-001
  - EP-01-003 implements VP-07-006
  - EP-01-003 depends-on DUR-01-001 (ISO 8601 duration format)
- `EP-01-004` The embargo policy record MUST be serializable as a Pydantic
  model and persisted in the DataLayer
- `EP-01-005` The embargo policy record MUST use full-URI IDs for `actor_id`
  - EP-01-005 depends-on OID-01-001

## API Endpoint

- `EP-02-001` `PROD_ONLY` Each Actor SHOULD expose its embargo policy at
  `GET /actors/{actor_id}/embargo-policy`
  - Response MUST use the policy record format defined in EP-01-001 through
    EP-01-003
  - Response MUST return HTTP 404 if the Actor has not declared a policy
- `EP-02-002` `PROD_ONLY` The policy endpoint MUST be machine-readable
  (returns JSON) and MUST be listed in the Actor's ActivityPub profile under
  a well-known key (e.g., `vultron:embargoPolicy`)

## Policy Compatibility Evaluation

- `EP-03-001` (SHOULD) `PROD_ONLY` Before proposing an embargo or inviting an actor
  to join an existing embargo, the CaseActor SHOULD retrieve and evaluate
  the target actor's embargo policy for compatibility with the proposed
  embargo terms
  - EP-03-001 implements VP-07-001
  - EP-03-001 implements VP-07-006
  - EP-03-001 implements VP-07-007
- `EP-03-002` `PROD_ONLY` Compatibility evaluation MUST check that the
  proposed duration falls within the target actor's
  `minimum_duration`–`maximum_duration` range, if declared
  - EP-03-002 implements VP-07-003
  - EP-03-002 implements VP-07-004
  - EP-03-002 implements VP-07-005
  - EP-03-002 depends-on DUR-01-001
  - EP-03-002 depends-on DUR-04-001

## Verification

### EP-01-001 through EP-01-004 Verification

- Unit test: `EmbargoPolicy` Pydantic model validates required fields
- Unit test: Serialization round-trip via `object_to_record` preserves all
  fields

### EP-02-001 Verification

- `PROD_ONLY` Integration test: `GET /actors/{id}/embargo-policy` returns
  200 with valid JSON for an actor with a declared policy
- `PROD_ONLY` Integration test: Returns 404 for an actor without a policy

### EP-03-001, EP-03-002 Verification

- `PROD_ONLY` Unit test: Compatibility check returns `True` when proposed
  duration is within range, `False` otherwise

## Default Embargo Semantics (MUST)

- `EP-04-001` When a receiver applies their published default embargo at case
  creation and the sender submitted no explicit embargo proposal, the initial
  `CaseStatus.em_state` MUST be set to `EM.ACTIVE`, not `EM.PROPOSED`. The
  sender's report submission without a counter-proposal constitutes tacit
  acceptance of the receiver's default embargo.
  - EP-04-001 implements the "Receiver Has Default Embargo, Sender Implies
    Acceptance" rule from `docs/topics/process_models/em/defaults.md`
  - EP-04-001 refines DUR-07-003 and CM-12-004
- `EP-04-002` The implementation MUST apply both the PROPOSE and ACCEPT state
  machine triggers atomically within `InitializeDefaultEmbargoNode`. The
  intermediate `EM.PROPOSED` state MUST NOT be persisted or observable
  externally.
  - Rationale: the EM state machine has no direct NONE→ACTIVE transition;
    the PROPOSE+ACCEPT sequence is the correct protocol path without
    changing the state machine definition.
- `EP-04-003` When both the sender and receiver have an applicable embargo
  proposal at case creation (sender proposes a duration and receiver has a
  default), the shorter of the two MUST be made active immediately
  (`em_state = EM.ACTIVE`) and the longer SHOULD be registered as a pending
  revision (`em_state = EM.REVISE`).
  - EP-04-003 implements the "shortest embargo wins" principle from
    `docs/topics/process_models/em/defaults.md`
- `EP-04-004` EP-04-003 is contingent on a sender-proposal mechanism being
  available. Until such a mechanism exists, only the no-sender-proposal case
  (EP-04-001) applies at case creation.
  - See `notes/embargo-default-semantics.md` for the known gap and design
    paths for the missing mechanism.

### EP-04 Verification

- Unit test: After `InitializeDefaultEmbargoNode` runs, `case.current_status.em_state`
  is `EM.ACTIVE` (not `EM.PROPOSED`)
- Unit test: The intermediate `EM.PROPOSED` state is never persisted to the
  DataLayer during default embargo initialization
- Unit test: Demo final-state assertions use `EM.ACTIVE`, not `EM.PROPOSED`,
  for the default-embargo case

## Related

- **Case Management**: `specs/case-management.md`
- **Response Format**: `specs/response-format.md`
- **Agentic Readiness**: `specs/agentic-readiness.md`
- **Object IDs**: `specs/object-ids.md`
- **Duration Format**: `specs/duration.md` (ISO 8601 duration string format)
- **EM Process Model**: `docs/topics/process_models/em/defaults.md`
