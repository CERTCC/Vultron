# Triggerable Behaviors: Design Notes

**Cross-references**: `plan/PRIORITIES.md` PRIORITY 30,
`specs/behavior-tree-integration.md` BT-08,
`docs/topics/behavior_logic/` (reference behavior tree docs),
`plan/IMPLEMENTATION_PLAN.md` Phase PRIORITY-30

---

## Background

The Vultron Protocol defines two categories of actor behavior:

1. **Reactive behaviors** — triggered by an incoming ActivityStreams message
   (already fully implemented via the handler pipeline).
2. **Triggerable behaviors** — initiated by the local actor based on their
   own internal state and decision-making, not in direct response to a
   message.

Triggerable behaviors are the counterpart to the inbound handler pipeline.
The full CVD protocol cannot be demonstrated without them; a complete
implementation requires both sides.

Reference documentation for the behavior trees these behaviors correspond to:

- `docs/topics/behavior_logic/rm_bt.md`
- `docs/topics/behavior_logic/rm_validation_bt.md`
- `docs/topics/behavior_logic/rm_prioritization_bt.md`
- `docs/topics/behavior_logic/rm_closure_bt.md`
- `docs/topics/behavior_logic/em_bt.md`
- `docs/topics/behavior_logic/em_eval_bt.md`
- `docs/topics/behavior_logic/em_propose_bt.md`

---

## Open Design Questions

### 1. Trigger Scope

Which behaviors should be individually triggerable via API? The reference
docs describe multi-step state machines with complex branching.

**Granularity**: The right level is **above** pure leaf nodes (which often
just perform condition checks and have no meaningful side effects on their
own) but **below** top-level orchestrators (e.g., "run all of Report
Management"). The target is **middle-layer nodes** that represent a
meaningful unit of work: a subtree that makes a coherent decision and
produces observable side effects. For example, triggering "Report
Validated" is appropriate — it evaluates the report, sends an `Accept` to
the reporter, triggers case creation, etc. Triggering the atomic leaf
condition-check node that `Report Validated` calls internally is not.

Rule of thumb: a trigger-worthy behavior has a recognizable name, performs
a meaningful CVD action, and generates at least one outgoing activity.

**Recommendation**: Prefer middle-layer triggers that map to named CVD
protocol actions (`validate_report`, `engage_case`, `defer_case`, etc.)
since these have clear semantics and map to existing BT subtrees.

### 2. Input and Output Schema

Minimum required input for a trigger endpoint:

- `actor_id` (from path parameter)
- Enough context to identify what is being acted on:
  - Report-scoped behaviors: `offer_id` (the specific `Offer(Report)` being
    acted on — a single report may have multiple outstanding offers, so the
    offer must be uniquely identified); `report_id` MAY also be provided as
    a confirmation check to guard against acting on an offer for a different
    report than intended
  - Case-scoped behaviors: `case_id` (which `VulnerabilityCase` is in scope)
- **Behavior-specific parameters** (optional but supported): some behaviors
  may accept additional data relevant to the action itself. For example:
  - `prioritize-case` could accept SSVC decision point selections or CVSS
    vector elements used by the prioritization logic
  - `propose-embargo` could accept proposed duration and any policy
    constraints
- **Optional note/content field**: most trigger endpoints SHOULD accept a
  free-text `note` field whose content can be embedded in the outgoing
  activity. For example, a `defer-case` trigger SHOULD accept a reason
  note that becomes the body of the `Ignore` activity sent to the case.

Response options:

- The resulting ActivityStreams activity (preferred for protocol alignment)
- A job ID with polling endpoint (needed for long-running behaviors)
- HTTP 202 with no body (simplest, acceptable for prototype)

**Recommendation**: Return the resulting activity for simple single-step
behaviors; defer job tracking to production (see `specs/agentic-readiness.md`
AR-04-001 `PROD_ONLY`).

### 3. Relationship to CLI Interface

`specs/behavior-tree-integration.md` BT-08-001 (MAY) permits a CLI interface
for BT execution. The HTTP trigger API and the CLI could share the same
underlying invocation logic. Design the endpoint contract first; the CLI
wraps it.

### 4. Overlap with Existing Inbound Handlers

Several inbound handlers (`validate_report`, `engage_case`, `defer_case`)
already invoke BT trees. The trigger API is the **outgoing counterpart** —
the local actor deciding to initiate the behavior. The BT tree itself is
the same; only the direction differs:

| Direction | Entry point | Example |
|-----------|-------------|---------|
| Inbound   | `POST /actors/{id}/inbox` | Receiver processes a `Submit` activity |
| Trigger   | `POST /actors/{id}/trigger/validate-report` | Actor decides locally to validate a report |

The trigger endpoint MUST ultimately produce an outgoing ActivityStreams
activity (via the actor's outbox) just as the inbound handler produces
state updates.

**Naming convention**: To avoid confusion between inbound handlers and
outbound triggers that wrap the same BT logic, function names SHOULD
reflect direction:

- `handle_validate_report` — processes an inbound `Submit` or related
  message; updates local state in response to the sender's assertion
- `trigger_validate_report` — local actor decides to validate a report;
  invokes the BT and emits an outgoing `Accept` or `Reject`

This distinction helps agents and maintainers identify which code paths
are reactive (inbound) versus initiative (outbound). Document naming
conventions in the relevant handler or trigger module docstring.

---

## Candidate Behaviors for PRIORITY 30

Based on `plan/PRIORITIES.md` and the reference behavior tree docs:

### RM Behaviors

| Behavior | BT reference | Description |
|----------|-------------|-------------|
| `validate-report` | `rm_validation_bt.md` | Actor validates a held report |
| `invalidate-report` | `rm_validation_bt.md` | Actor invalidates a held report |
| `engage-case` | `rm_prioritization_bt.md` | Actor accepts/engages with a case |
| `defer-case` | `rm_prioritization_bt.md` | Actor defers/deprioritizes a case |
| `close-report` | `rm_closure_bt.md` | Actor closes a report |

### EM Behaviors

| Behavior | BT reference | Description |
|----------|-------------|-------------|
| `propose-embargo` | `em_propose_bt.md` | Actor proposes an embargo to case participants |
| `evaluate-embargo` | `em_eval_bt.md` | Actor evaluates an existing embargo proposal |
| `terminate-embargo` | `em_bt.md` | Actor announces embargo termination |

---

## Endpoint Design Sketch

```http
POST /actors/{actor_id}/trigger/{behavior-name}
Content-Type: application/json

{
  "offer_id":  "...",   // for report-scoped behaviors (required)
  "report_id": "...",   // confirmation check for report-scoped behaviors
  "case_id":   "...",   // for case-scoped behaviors
  "params":    { ... }, // behavior-specific parameters (e.g., SSVC values)
  "note":      "..."    // optional free-text; embedded in outgoing activity
}
```

Response on success:

```http
HTTP 202 Accepted
Content-Type: application/json

{
  "activity": { ... }   // the resulting ActivityStreams activity
}
```

A formal spec SHOULD be drafted (see `plan/IMPLEMENTATION_PLAN.md` P30-1)
before implementing.

---

## Relationship to Actor Independence (PRIORITY 100)

Triggerable behaviors are scoped to a single actor's internal state. The
trigger endpoint MUST resolve the correct per-actor DataLayer instance from
`actor_id`. This dependency exists whether or not full actor independence
(PRIORITY 100) is implemented. Design trigger endpoints to accept a
DataLayer instance via dependency injection so that per-actor isolation
can be retrofitted later without changing the endpoint contract.

**See**: `notes/domain-model-separation.md` "Per-Actor DataLayer Options"
for isolation design options.
