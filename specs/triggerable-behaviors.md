# Triggerable Behaviors Specification

## Overview

Requirements for the trigger API that allows an actor to initiate
protocol behaviors based on their own internal state, rather than
reacting to an inbound ActivityStreams message.

Triggerable behaviors are the **outgoing counterpart** to the inbound
handler pipeline. The full CVD protocol cannot be demonstrated without
them; a complete implementation requires both reactive and triggerable sides.

**Source**: `plan/PRIORITIES.md` (Priority 30),
`notes/triggerable-behaviors.md` (design notes),
`docs/topics/behavior_logic/` (reference behavior tree docs)

**Cross-references**: `behavior-tree-integration.md` (BT-08),
`case-management.md` (CM-01), `handler-protocol.md` (HP-00-001),
`outbox.md` (OX-02-001), `agentic-readiness.md` (AR-04, AR-08)

---

## Endpoint Format (MUST)

- `TB-01-001` The system MUST expose trigger endpoints using the path
  pattern `POST /actors/{actor_id}/trigger/{behavior-name}`
  - `actor_id`: the locally-hosted actor initiating the behavior
  - `behavior-name`: a kebab-case identifier matching the behavior table
    in `TB-02-001` and `TB-02-002`
- `TB-01-002` Trigger endpoints MUST return HTTP 202 on successful
  acceptance
  - TB-01-002 depends-on HTTP-01-003
- `TB-01-003` Trigger endpoints MUST return a structured error response
  when the actor, case, or report referenced in the request body cannot
  be resolved
  - TB-01-003 depends-on EH-05-001
- `TB-01-004` Trigger endpoint processing MUST NOT block the HTTP
  response; long-running behavior execution MUST run as a background task
  - TB-01-004 depends-on IE-03-001

---

## Candidate RM Behaviors (SHOULD)

- `TB-02-001` The following RM behaviors SHOULD be individually
  triggerable via the trigger API:

  | `behavior-name`        | BT reference              | Description |
  |------------------------|---------------------------|-------------|
  | `validate-report`      | `rm_validation_bt.md`     | Actor accepts the offered report (soft-valid path) |
  | `invalidate-report`    | `rm_validation_bt.md`     | Actor tentatively rejects the offered report |
  | `reject-report`        | `rm_validation_bt.md`     | Actor hard-closes the offered report (Reject) |
  | `engage-case`          | `rm_prioritization_bt.md` | Actor engages with a case |
  | `defer-case`           | `rm_prioritization_bt.md` | Actor deprioritizes a case |
  | `close-report`         | `rm_closure_bt.md`        | Actor closes a report |

  **Note**: Report validation has three distinct outcomes —
  `Accept(Offer(Report))`, `TentativelyReject(Offer(Report))`, and
  `Reject(Offer(Report))` — corresponding to `validate-report`,
  `invalidate-report`, and `reject-report` respectively. See
  `notes/triggerable-behaviors.md` for details on the three-way split
  and its implications for documentation updates to `rm_validation_bt.md`.

---

## Candidate EM Behaviors (SHOULD)

- `TB-02-002` The following EM behaviors SHOULD be individually
  triggerable via the trigger API:

  | `behavior-name`      | BT reference        | Description |
  |----------------------|---------------------|-------------|
  | `propose-embargo`    | `em_propose_bt.md`  | Actor proposes an embargo |
  | `evaluate-embargo`   | `em_eval_bt.md`     | Actor evaluates an embargo proposal |
  | `terminate-embargo`  | `em_bt.md`          | Actor announces embargo termination |

---

## Additional Candidate Behaviors (MAY)

- `TB-02-003` The following additional behaviors MAY be individually
  triggerable via the trigger API in a later phase:

  | `behavior-name`          | BT reference                  | Description |
  |--------------------------|-------------------------------|-------------|
  | `notify-actor`           | `report_to_others_bt.md`      | Actor invites a new participant to a case |
  | `assign-cve-id`          | `id_assignment_bt.md`         | Actor assigns or records a CVE ID for a case |
  | `identify-participants`  | `identify_participants_bt.md` | Actor identifies potential new participants |

---

## Request Body (MUST)

- `TB-03-001` The trigger endpoint request body MUST be a JSON object
  containing sufficient context to identify the target report or case:
  - Report-scoped behaviors (`validate-report`, `invalidate-report`,
    `reject-report`, `close-report`): MUST include `offer_id`; MAY include
    `report_id` as a confirmation guard against acting on an offer for the
    wrong report
  - Case-scoped behaviors (`engage-case`, `defer-case`, `propose-embargo`,
    `evaluate-embargo`, `terminate-embargo`, `notify-actor`,
    `assign-cve-id`, `identify-participants`): MUST include `case_id`
- `TB-03-002` Unknown fields in the request body MUST be ignored
  (forward-compatibility)
- `TB-03-003` The trigger endpoint request body SHOULD support an optional
  `note` field containing free-text content that will be embedded in the
  outgoing ActivityStreams activity (e.g., reason for rejection, rationale
  for embargo proposal)

---

## Response Body (SHOULD)

- `TB-04-001` A successful trigger response SHOULD include the resulting
  ActivityStreams activity in the response body under an `activity` key:

  ```json
  {
    "activity": { "type": "...", "actor": "...", ... }
  }
  ```

- `TB-04-002` `PROD_ONLY` When a trigger initiates a long-running
  behavior, the response MAY return a job object per `AR-04-001`
  instead of the activity directly
  - TB-04-002 depends-on AR-04-001

---

## BT Integration (SHOULD)

- `TB-05-001` Trigger endpoint implementations SHOULD reuse existing
  BT trees rather than duplicating behavior logic
  - The trigger API is the outgoing side; the BT tree is the same
    regardless of direction (inbound handler vs actor-initiated trigger)
- `TB-05-002` The trigger endpoint SHOULD invoke the BT tree via the
  bridge layer (`vultron/behaviors/bridge.py`) using the same pattern
  as existing BT-using handlers
  - TB-05-002 depends-on BT-05-001

---

## Per-Actor DataLayer (MUST)

- `TB-06-001` Trigger endpoints MUST resolve the correct per-actor
  DataLayer instance using the `actor_id` path parameter
  - The same dependency injection mechanism used for inbox handlers
    MUST be used for trigger endpoints
  - TB-06-001 depends-on CM-01-001
- `TB-06-002` Trigger endpoint implementations MUST accept the DataLayer
  instance via dependency injection to allow per-actor isolation to be
  retrofitted without changing endpoint contracts
  - TB-06-002 depends-on CM-01-001

---

## Outbox Activity (MUST)

- `TB-07-001` A successfully executed trigger MUST produce an outgoing
  ActivityStreams activity added to the actor's outbox
  - The trigger causes the activity; the activity is not the trigger
  - TB-07-001 depends-on OX-02-001

---

## Verification

### TB-01-001, TB-01-002, TB-01-003, TB-01-004 Verification

- Integration test: `POST /actors/{id}/trigger/validate-report` with
  valid `offer_id` returns HTTP 202
- Integration test: Request with unknown `actor_id` returns structured
  error per EH-05-001
- Integration test: HTTP 202 returned before behavior execution completes

### TB-02-001, TB-02-002, TB-02-003 Verification

- Integration test: Each named behavior endpoint exists and accepts
  a valid request body
- Unit test: Unrecognized `behavior-name` returns HTTP 404

### TB-03-001, TB-03-002, TB-03-003 Verification

- Unit test: Request missing required context field returns HTTP 422
  (Unprocessable Entity) with field-level error
- Unit test: Unknown fields in request body are silently ignored
- Integration test: Trigger with `note` field embeds content in outgoing
  activity

### TB-04-001 Verification

- Integration test: Successful trigger response body contains an
  `activity` key with a valid ActivityStreams activity

### TB-05-001, TB-05-002 Verification

- Code review: Trigger implementations call existing BT trees via
  `vultron/behaviors/bridge.py`
- Unit test: BT execution result is reflected in response activity

### TB-06-001, TB-06-002 Verification

- Unit test: `actor_id` in path resolves to a distinct DataLayer instance
- Code review: DataLayer injected via dependency, not accessed as singleton

### TB-07-001 Verification

- Integration test: After successful trigger, actor outbox contains the
  resulting activity

---

## Related

- **Design Notes**: `notes/triggerable-behaviors.md` (open questions,
  endpoint sketch, candidate behavior table)
- **Behavior Trees**: `specs/behavior-tree-integration.md` (BT-08 CLI,
  BT-09 actor isolation)
- **Actor Isolation**: `specs/case-management.md` (CM-01)
- **Handler Protocol**: `specs/handler-protocol.md` (HP-00-001)
- **Outbox**: `specs/outbox.md` (OX-02-001)
- **Agentic Readiness**: `specs/agentic-readiness.md` (AR-04, AR-08)
- **Prototype Shortcuts**: `specs/prototype-shortcuts.md` (PROD_ONLY deferral)
- **Implementation**: `plan/IMPLEMENTATION_PLAN.md` Phase PRIORITY-30
  (P30-1 through P30-6)
- **Priorities**: `plan/PRIORITIES.md` PRIORITY 30
- **BT docs**: `docs/topics/behavior_logic/rm_bt.md`,
  `docs/topics/behavior_logic/em_bt.md` (reference behavior tree docs)
