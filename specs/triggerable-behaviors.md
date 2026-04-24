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
`notes/trigger-classification.md` (classification decisions),
`docs/topics/behavior_logic/` (reference behavior tree docs)

**Cross-references**: `behavior-tree-integration.md` (BT-08),
`case-management.md` (CM-01), `handler-protocol.md` (HP-00-001),
`outbox.md` (OX-02-001), `agentic-readiness.md` (AR-04, AR-08),
`configuration.md` (CFG-04)

---

## Endpoint Format

- `TRIG-01-001` The system MUST expose trigger endpoints using the path
  pattern `POST /actors/{actor_id}/trigger/{behavior-name}`
  - `actor_id`: the locally-hosted actor initiating the behavior
  - `behavior-name`: a kebab-case identifier matching the behavior table
    in `TRIG-02-001` and `TRIG-02-002`
- `TRIG-01-002` Trigger endpoints MUST return HTTP 202 on successful
  acceptance
  - TRIG-01-002 depends-on HTTP-01-003
- `TRIG-01-003` Trigger endpoints MUST return a structured error response
  when the actor, case, or report referenced in the request body cannot
  be resolved
  - TRIG-01-003 depends-on EH-05-001
- `TRIG-01-004` Trigger endpoint processing MUST NOT block the HTTP
  response; long-running behavior execution MUST run as a background task
  - TRIG-01-004 depends-on IE-03-001
- `TRIG-01-005` Trigger endpoints MUST be synchronous from the caller's
  perspective: the response MUST be returned only after the triggered
  behavior completes (or fails)
  - **Rationale**: Unlike inbound message handlers (which are intentionally
    asynchronous because they react to remote actors), triggerable behaviors
    are initiated locally and the caller expects an immediate result
  - TRIG-01-005 refines TRIG-01-004 (the no-block constraint applies to
    HTTP I/O machinery, not to the behavior execution itself)

---

## Candidate RM Behaviors

- `TRIG-02-001` The following RM behaviors SHOULD be individually
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

## Candidate EM Behaviors

- `TRIG-02-002` The following EM behaviors SHOULD be individually
  triggerable via the trigger API:

  | `behavior-name`            | BT reference        | Description |
  |----------------------------|---------------------|-------------|
  | `propose-embargo`          | `em_propose_bt.md`  | Actor proposes an embargo |
  | `accept-embargo`           | `em_eval_bt.md`     | Actor accepts an embargo proposal |
  | `reject-embargo`           | `em_eval_bt.md`     | Actor rejects an embargo proposal |
  | `propose-embargo-revision` | `em_propose_bt.md`  | Actor proposes a revision to an active embargo |
  | `terminate-embargo`        | `em_bt.md`          | Actor announces embargo termination |

---

## Candidate Case Management Behaviors

- `TRIG-02-004` The following case management behaviors SHOULD be individually
  triggerable via the trigger API:

  | `behavior-name`        | BT reference           | Description |
  |------------------------|------------------------|-------------|
  | `create-case`          | `rm_case_bt.md`        | Actor creates a new VulnerabilityCase and notifies the CaseActor |
  | `add-report-to-case`   | `rm_case_bt.md`        | Actor links an existing VulnerabilityReport to a VulnerabilityCase (delegates to `add-object-to-case` after type validation) |
  | `add-object-to-case`   | `add_note_bt.md`       | Actor adds any AS2 object to a case and broadcasts it to all participants |
  | `submit-report`        | `rm_submit_bt.md`      | Actor (finder) creates and offers a VulnerabilityReport to a vendor |

---

## Candidate Participant Management Behaviors

- `TRIG-02-005` The following participant management behaviors SHOULD be
  individually triggerable via the trigger API:

  | `behavior-name`          | BT reference               | Description |
  |--------------------------|----------------------------|-------------|
  | `suggest-actor-to-case`  | `rm_notify_bt.md`          | Actor recommends another actor to the case owner for invitation |
  | `invite-actor-to-case`   | `rm_notify_bt.md`          | Case owner directly invites an actor to participate in a case |
  | `accept-case-invite`     | `rm_accept_invite_bt.md`   | Invited actor accepts an RmInviteToCaseActivity |

  **Note**: The `suggest-actor-to-case` → `invite-actor-to-case` → `accept-case-invite`
  sequence is a concrete example of a protocol event cascade. See
  `notes/protocol-event-cascades.md` for the full 4-step cascade description.

---

## Demo-Only Trigger Behaviors

- `TRIG-02-006` The following behaviors exist only to support demo and
  prototype scenarios. They are exposed under the `/demo/` URL prefix
  (see TRIG-09-001) and MUST NOT be mounted in production mode
  (see TRIG-09-002):

  | `behavior-name`      | Generalizes from         | Description |
  |----------------------|--------------------------|-------------|
  | `add-note-to-case`   | `add-object-to-case`     | Demo-specific shortcut: adds a Note to a case (type pre-selected for demo convenience) |
  | `sync-log-entry`     | *(cascade — no general trigger)* | Manually commits a SYNC log entry; in a real system this cascades automatically from state-changing operations |

  **Rationale**: Demo-only triggers are behaviors that an autonomous actor
  with a working BT would never need to have externally driven. They exist
  because demos must puppeteer actors to demonstrate the protocol; they are
  not legitimate external stimuli or explicit actor decisions. See
  `notes/trigger-classification.md` for the full classification rationale
  and audit results.

---

## Additional Candidate Behaviors

- `TRIG-02-003` The following additional behaviors MAY be individually
  triggerable via the trigger API in a later phase:

  | `behavior-name`          | BT reference                  | Description |
  |--------------------------|-------------------------------|-------------|
  | `notify-actor`           | `report_to_others_bt.md`      | Actor invites a new participant to a case |
  | `assign-cve-id`          | `id_assignment_bt.md`         | Actor assigns or records a CVE ID for a case |
  | `identify-participants`  | `identify_participants_bt.md` | Actor identifies potential new participants |

---

## Request Body

- `TRIG-03-001` The trigger endpoint request body MUST be a JSON object
  containing sufficient context to identify the target report or case:
  - Report-scoped behaviors (`validate-report`, `invalidate-report`,
    `reject-report`, `close-report`, `submit-report`): MUST include
    `offer_id`; MAY include `report_id` as a confirmation guard against
    acting on an offer for the wrong report. The `submit-report` behavior
    uses `report_id` directly.
  - Case-scoped behaviors (`engage-case`, `defer-case`, `propose-embargo`,
    `accept-embargo`, `reject-embargo`, `propose-embargo-revision`,
    `terminate-embargo`, `add-object-to-case`, `add-report-to-case`,
    `create-case`, `invite-actor-to-case`, `suggest-actor-to-case`,
    `notify-actor`, `assign-cve-id`, `identify-participants`):
    MUST include `case_id`
  - Invite-scoped behaviors (`accept-case-invite`): MUST include `invite_id`
- `TRIG-03-002` Unknown fields in the request body MUST be ignored
  (forward-compatibility)
- `TRIG-03-003` The trigger endpoint request body SHOULD support an optional
  `note` field containing free-text content that will be embedded in the
  outgoing ActivityStreams activity (e.g., rationale for embargo proposal,
  reason for deferral)
- `TRIG-03-004` The `reject-report` trigger request body MUST include a
  `note` field (reason required); the `note` value SHOULD be non-empty
  - **Rationale**: Hard-close decisions are irreversible and warrant
    documented justification for audit purposes
  - TRIG-03-004 refines TRIG-03-003
  - TRIG-03-004 depends-on CS-08-001

---

## Response Body

- `TRIG-04-001` A successful trigger response SHOULD include the resulting
  ActivityStreams activity in the response body under an `activity` key:

  ```json
  {
    "activity": { "type": "...", "actor": "...", ... }
  }
  ```

- `TRIG-04-002` (MAY) `PROD_ONLY` When a trigger initiates a long-running
  behavior, the response MAY return a job object per `AR-04-001`
  instead of the activity directly
  - TRIG-04-002 depends-on AR-04-001

---

## BT Integration

- `TRIG-05-001` Trigger endpoint implementations SHOULD reuse existing
  BT trees rather than duplicating behavior logic
  - The trigger API is the outgoing side; the BT tree is the same
    regardless of direction (inbound handler vs actor-initiated trigger)
- `TRIG-05-002` The trigger endpoint SHOULD invoke the BT tree via the
  bridge layer (`vultron/core/behaviors/bridge.py`) using the same pattern
  as existing BT-using handlers
  - TRIG-05-002 depends-on BT-05-001

---

## Per-Actor DataLayer

- `TRIG-06-001` Trigger endpoints MUST resolve the correct per-actor
  DataLayer instance using the `actor_id` path parameter
  - The same dependency injection mechanism used for inbox handlers
    MUST be used for trigger endpoints
  - TRIG-06-001 depends-on CM-01-001
- `TRIG-06-002` Trigger endpoint implementations MUST accept the DataLayer
  instance via dependency injection to allow per-actor isolation to be
  retrofitted without changing endpoint contracts
  - TRIG-06-002 depends-on CM-01-001

---

## Outbox Activity

- `TRIG-07-001` A successfully executed trigger MUST produce an outgoing
  ActivityStreams activity added to the actor's outbox
  - The trigger causes the activity; the activity is not the trigger
  - TRIG-07-001 depends-on OX-02-001

---

## Trigger Classification

- `TRIG-08-001` The application MUST define a `RunMode` StrEnum with at
  least two values: `PROTOTYPE` and `PROD`
  - The enum MUST use `StrEnum` so comparisons are string-safe and do not
    rely on bare string matching
  - `RunMode` MUST be importable from a neutral shared module
    (e.g., `vultron/enums.py` or `vultron/config.py`)
- `TRIG-08-002` A trigger is **general-purpose** if it represents either
  a legitimate external stimulus (e.g., a finder submitting a report) or
  an intentional actor decision that a human operator or agentic client
  might initiate (e.g., validating a report, proposing an embargo).
  A trigger is **demo-only** if the only reason it exists is to let a demo
  script puppeteer an actor through a step the actor's own BT would handle
  autonomously in a real deployment.
  - This distinction is captured in `notes/trigger-classification.md`
    (decision table and audit results)
- `TRIG-08-003` General-purpose triggers MUST be exposed under the path
  prefix `/actors/{actor_id}/trigger/{behavior-name}` (TRIG-01-001)
- `TRIG-08-004` Demo-only triggers MUST be exposed under the path prefix
  `/actors/{actor_id}/demo/{behavior-name}` (see TRIG-09-001)
- `TRIG-08-005` `RunMode` MUST be stored as `ServerConfig.run_mode` within
  `AppConfig` (CFG-04-001) with a default of `RunMode.PROTOTYPE`
  - The environment variable override is `VULTRON_SERVER__RUN_MODE`
    (CFG-03-001, CFG-03-002)
  - TRIG-08-005 depends-on CFG-04-001

---

## Demo Trigger Endpoints

- `TRIG-09-001` Demo-only trigger endpoints MUST use the URL path pattern
  `POST /actors/{actor_id}/demo/{behavior-name}`
  - This prefix is distinct from the general-purpose `/trigger/` prefix
    so that the distinction is visible in logs, API clients, and OpenAPI
    documentation
- `TRIG-09-002` The demo router MUST be conditionally mounted: it MUST be
  included in the FastAPI application only when
  `get_config().server.run_mode == RunMode.PROTOTYPE`
- `TRIG-09-003` When `run_mode == RunMode.PROD`, any request to a path
  under `/demo/` MUST return HTTP 404 (the routes are not mounted; no
  custom error message is required)
  - TRIG-09-003 depends-on TRIG-09-002
- `TRIG-09-004` Demo trigger endpoints MUST share the same per-actor
  DataLayer injection pattern as general-purpose trigger endpoints
  (TRIG-06-001, TRIG-06-002)
- `TRIG-09-005` Demo trigger endpoints MUST use an OpenAPI tag that
  visually distinguishes them from general-purpose triggers in the Swagger
  UI (e.g., `tags=["Demo Triggers"]` vs `tags=["Triggers"]`)

---

## Generalized Object Triggers and Type-Specific Wrappers

- `TRIG-10-001` The system MUST expose an `add-object-to-case` general
  trigger at `POST /actors/{actor_id}/trigger/add-object-to-case` that
  accepts any valid AS2 object type as the `object` in its request body
  - **Rationale**: Adding content to a case is a legitimate operator action
    regardless of object type; a Note is the most common use but not the
    only one
- `TRIG-10-002` Type-specific convenience triggers (e.g., `add-report-to-case`)
  MUST delegate to the corresponding general trigger after performing
  type-specific validation
  - Example: `add-report-to-case` validates that the referenced object is
    a `VulnerabilityReport`, then delegates to the `add-object-to-case`
    use-case implementation
  - This avoids duplicating case-add logic across multiple endpoints
- `TRIG-10-003` `add-note-to-case` MUST NOT be exposed as a general
  `/trigger/` endpoint; it MUST be moved to `/demo/add-note-to-case` as
  a demo-only convenience wrapper around `add-object-to-case`
  - TRIG-10-003 refines TRIG-08-004
- `TRIG-10-004` `sync-log-entry` MUST NOT be exposed as a general
  `/trigger/` endpoint; it MUST be moved to `/demo/sync-log-entry`
  - **Rationale**: In a correct implementation, SYNC log entries are
    committed automatically as a cascade effect of every state-changing
    operation. An explicit trigger exists only to let the demo script inject
    entries manually. A future production "force-sync" recovery operation
    would require a protocol-level mechanism for a peer to advertise its
    current log tail hash before entries are replayed (SYNC-03-004)
  - TRIG-10-004 refines TRIG-08-004

---

## Verification

### TRIG-01-001, TRIG-01-002, TRIG-01-003, TRIG-01-004 Verification

- Integration test: `POST /actors/{id}/trigger/validate-report` with
  valid `offer_id` returns HTTP 202
- Integration test: Request with unknown `actor_id` returns structured
  error per EH-05-001
- Integration test: HTTP 202 returned before behavior execution completes

### TRIG-02-001, TRIG-02-002, TRIG-02-003, TRIG-02-004, TRIG-02-005 Verification

- Integration test: Each named behavior endpoint exists and accepts
  a valid request body
- Unit test: Unrecognized `behavior-name` returns HTTP 404

### TRIG-03-001, TRIG-03-002, TRIG-03-003, TRIG-03-004 Verification

- Unit test: Request missing required context field returns HTTP 422
  (Unprocessable Entity) with field-level error
- Unit test: Unknown fields in request body are silently ignored
- Integration test: Trigger with `note` field embeds content in outgoing
  activity
- Unit test: `reject-report` trigger request missing `note` field returns
  HTTP 422
- Unit test: `reject-report` trigger with empty `note` emits a warning

### TRIG-04-001 Verification

- Integration test: Successful trigger response body contains an
  `activity` key with a valid ActivityStreams activity

### TRIG-05-001, TRIG-05-002 Verification

- Code review: Trigger implementations call existing BT trees via
  `vultron/core/behaviors/bridge.py`
- Unit test: BT execution result is reflected in response activity

### TRIG-06-001, TRIG-06-002 Verification

- Unit test: `actor_id` in path resolves to a distinct DataLayer instance
- Code review: DataLayer injected via dependency, not accessed as singleton

### TRIG-07-001 Verification

- Integration test: After successful trigger, actor outbox contains the
  resulting activity

### TRIG-08-001, TRIG-08-002, TRIG-08-003, TRIG-08-004, TRIG-08-005 Verification

- Code review: `RunMode` is a `StrEnum` importable from a neutral module
- Unit test: `AppConfig().server.run_mode` defaults to `RunMode.PROTOTYPE`
- Unit test: `VULTRON_SERVER__RUN_MODE=prod` yields `RunMode.PROD`
- Code review: General-purpose trigger routers use `/trigger/` prefix;
  demo-only trigger routers use `/demo/` prefix

### TRIG-09-001, TRIG-09-002, TRIG-09-003, TRIG-09-004, TRIG-09-005 Verification

- Unit test: With `run_mode == PROD`, `POST /actors/{id}/demo/add-note-to-case`
  returns HTTP 404
- Unit test: With `run_mode == PROTOTYPE`, the demo router is mounted and
  demo endpoints return HTTP 202
- Code review: Demo trigger endpoints inject DataLayer via the same
  dependency as general trigger endpoints
- Code review: Demo trigger endpoints carry `tags=["Demo Triggers"]`
  in the OpenAPI metadata

### TRIG-10-001, TRIG-10-002, TRIG-10-003, TRIG-10-004 Verification

- Integration test: `POST /actors/{id}/trigger/add-object-to-case` with
  a Note object succeeds
- Integration test: `POST /actors/{id}/trigger/add-report-to-case`
  delegates to `add-object-to-case` logic and succeeds
- Unit test: `POST /actors/{id}/trigger/add-note-to-case` returns HTTP 404
  (endpoint does not exist under `/trigger/`)
- Unit test: `POST /actors/{id}/trigger/sync-log-entry` returns HTTP 404
  (endpoint does not exist under `/trigger/`)

---

## Related

- **Design Notes**: `notes/triggerable-behaviors.md` (open questions,
  endpoint sketch, candidate behavior table)
- **Classification Notes**: `notes/trigger-classification.md` (decision
  table, RunMode config, wrapper pattern, audit results)
- **Behavior Trees**: `specs/behavior-tree-integration.md` (BT-08 CLI,
  BT-09 actor isolation)
- **Actor Isolation**: `specs/case-management.md` (CM-01)
- **Handler Protocol**: `specs/handler-protocol.md` (HP-00-001)
- **Outbox**: `specs/outbox.md` (OX-02-001)
- **Agentic Readiness**: `specs/agentic-readiness.md` (AR-04, AR-08)
- **Configuration**: `specs/configuration.md` (CFG-04)
- **Sync Log Replication**: `specs/sync-log-replication.md` (SYNC-03-004)
- **Prototype Shortcuts**: `specs/prototype-shortcuts.md` (PROD_ONLY deferral)
- **Implementation**: `plan/IMPLEMENTATION_PLAN.md` Phase PRIORITY-30
  (P30-1 through P30-6)
- **Priorities**: `plan/PRIORITIES.md` PRIORITY 30
- **BT docs**: `docs/topics/behavior_logic/rm_bt.md`,
  `docs/topics/behavior_logic/em_bt.md` (reference behavior tree docs)
