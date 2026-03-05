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
| `validate-report` | `rm_validation_bt.md` | Actor accepts the offered report |
| `invalidate-report` | `rm_validation_bt.md` | Actor tentatively rejects the offered report |
| `reject-report` | `rm_validation_bt.md` | Actor hard-closes the offered report |
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

---

## BT Node Classification: Condition Checks, Evaluation Tasks, Execution Tasks

When analyzing which nodes in a BT sub-tree are candidates for triggerable
behaviors, it helps to classify each node by type:

- **Condition checks** — evaluate a boolean fact about the current state
  (e.g., "is report valid?", "is EM state ACTIVE?", "timer expired?").
  These map directly to DataLayer queries or computed properties and do not
  need to be exposed as triggerable behaviors on their own.

- **Evaluation tasks** — require judgment or assessment that cannot be
  fully automated from available data alone. Examples: "evaluate
  credibility", "evaluate priority", "evaluate embargo terms", "stop
  trying?", "current terms ok?". In the original simulation these were
  represented as fuzzer nodes (see `notes/bt-fuzzer-nodes.md`). In a real
  implementation they become either: (a) calls to a human-in-the-loop
  interface, (b) LLM-assisted evaluators with structured prompts, or (c)
  policy-rule evaluators for cases where the logic can be fully specified.

- **Execution tasks** — perform a concrete action with observable side
  effects: emitting a protocol message ("emit RV", "emit EA"), updating
  case state, creating objects. These are the natural units for triggerable
  behaviors.

The documentation in `docs/topics/behavior_logic/` uses these node types
in diagrams (condition nodes use "stadium" shape in Mermaid). However,
the diagrams were built by hand and may contain inconsistencies; use the
accompanying text as the authoritative source when diagrams disagree.

---

## Three-Way Report Validation

The current `rm_validation_bt.md` documentation describes a binary
outcome (valid / invalid), but the protocol and implementation support
three distinct outcomes:

| Outcome | Protocol message | Trigger behavior | Semantics |
|---------|-----------------|-----------------|-----------|
| Accept | `Accept(Offer(Report))` | `validate-report` | Report is credible and in scope; case creation follows |
| Tentative reject | `TentativelyReject(Offer(Report))` | `invalidate-report` | Report cannot be validated yet ("soft close") |
| Hard reject | `Reject(Offer(Report))` | `reject-report` | Report is definitively out of scope or invalid ("hard close") |

**Documentation gap**: The "D" branch of `rm_validation_bt.md` currently
only models the soft-close (TentativelyReject) path. It SHOULD be split
into:

1. A condition: "reject outright?" (is the report clearly out of scope or
   fraudulent?)
2. A hard-close branch emitting `Reject(Offer(Report))`
3. The existing soft-close branch emitting `TentativelyReject(Offer(Report))`

The evaluation nodes in the "C" branch (evaluate credibility / evaluate
validity) SHOULD produce structured outputs (e.g., `credible: bool`,
`valid: bool`, plus optional analyst notes) that feed into a policy
evaluation step determining which of the three outcomes to produce. These
values need not be strictly binary in a full implementation; intermediate
confidence levels may be appropriate.

**Open Question**: Should the `reject-report` trigger accept a mandatory
`note` field (reason required) to encourage documentation of hard-close
decisions? (blocks TB-03-003 refinement)

---

## Side Effects of "Emit FOO" Behaviors

The diagrams in `docs/topics/behavior_logic/` simplify "emit FOO" nodes to
look like single-message outputs. In practice each execution task may have
cascading side effects. Implementers MUST capture all relevant side effects
in the BT structure for each triggerable behavior, even when they are not
shown in the original diagram.

Known side effects by behavior:

| Behavior | Side effects beyond sending the message |
|---|---|
| `validate-report` (emit RV) | Create `VulnerabilityCase`; link reporter as participant; set receiver as case owner; trigger embargo resolution; link `VulnerabilityReport` to case |
| `reject-report` (emit RI hard) | Close the offer; log reason; no case created |
| `engage-case` (emit RA) | Update participant RM state to ACTIVE; log event |
| `defer-case` (emit RD) | Update participant RM state to DEFERRED; log event |
| `close-report` | Update RM state; log event; potentially trigger downstream notifications |
| `terminate-embargo` (emit ET) | Update `CaseStatus.em_state`; notify all participants; log reason |
| `propose-embargo` (emit EV/EP) | Create or update `EmbargoEvent` on case; notify participants |
| `evaluate-embargo` (emit EA) | Update local embargo acceptance state; send Accept/Reject |

The above is a non-exhaustive list. As implementation proceeds, each
triggerable behavior SHOULD document its full side-effect list in its
implementation module docstring.

---

## Placeholder Behaviors and Logging

Some execution nodes in the BT docs represent local processes whose
implementation details are outside the scope of the current prototype.
Examples: "close report" (internal workflow), "accept" / "defer" (internal
priority queue updates), "exit embargo" (external notification), "gather info".

These placeholder nodes MUST:

1. Log a structured event at INFO level when executed (so the behavior is
   observable in logs even if no external action is taken).
2. Return SUCCESS to allow the BT to continue (they are not blocking).
3. Be clearly labeled as placeholders in code (e.g., with a docstring
   comment like `# Placeholder: implement external callback in production`).

**Design Decision**: Placeholder nodes serve as future callback hooks.
Do NOT remove them — they are the correct place to attach future
integrations (task queues, webhook callbacks, ITSM integrations, etc.).

---

## SSVC-Based Prioritization

The "evaluate priority" node in `rm_prioritization_bt.md` is a judgment
call that in a full implementation maps to SSVC
(Stakeholder-Specific Vulnerability Categorization) evaluation.

Proposed implementation path:

1. **Collect case data**: Gather known facts about the vulnerability
   (report content, case state, embargo status, participant roles).
2. **Evaluate decision points**: For each SSVC decision point (e.g.,
   Exploitation, Automatable, Impact), either:
   - Apply a rule-based evaluator if the answer can be derived from
     structured case data.
   - Prompt a human or LLM evaluator: present the case context and ask
     the evaluator to select the best answer from the allowed values, with
     reasoning. The prompt SHOULD instruct the evaluator to "select all
     answers that cannot be ruled out" to err on the side of caution.
3. **Apply decision table**: Feed the selected decision point values into
   an SSVC `DecisionTable` to produce a prioritization outcome.
4. **Map to RM state**: For the prototype, map the SSVC outcome to
   binary `engage` / `defer`. In a full implementation the full SSVC
   outcome set (e.g., Track, Track*, Attend, Act) MAY be supported.

The `engage-case` / `defer-case` triggers directly correspond to this
engage/defer binary. The "accept" and "defer" placeholder nodes in
`rm_prioritization_bt.md` represent internal priority queue actions
(not the protocol messages). They should succeed unconditionally in
the prototype.

**See also**: `notes/bt-fuzzer-nodes.md` (SSVC-adjacent fuzzer nodes),
`specs/prototype-shortcuts.md` PROTO-05-001 (prioritization stub policy).

---

## Per-Behavior Design Notes

### Embargo Evaluation (evaluate-embargo)

"evaluate" in the embargo tree has two layers:

1. **Mechanical evaluation** (automatable): Does the proposed embargo have
   a valid end date? Is the duration within the actor's policy limits?
   (See `specs/embargo-policy.md`.) Does it follow the practices in
   `docs/topics/process_models/em/`?

2. **Judgment evaluation** (human-in-the-loop or LLM-assisted): Is the
   embargo duration proportionate to the case? Is the justification
   reasonable? Are the terms commensurate with the coordinating parties'
   constraints?

**Design Decision**: Implement the mechanical layer first. Stub the
judgment layer as a placeholder that always returns SUCCESS.

### Embargo Proposal (propose-embargo)

"Select terms" during embargo proposal is a judgment call that CAN be
stubbed as "apply default embargo policy" (see
`docs/topics/process_models/em/defaults.md`). The stub SHOULD:

1. Load the actor's `embargo_policy` record (see `specs/embargo-policy.md`).
2. Apply the preferred duration as the proposed term.
3. Log the selection.

A "customize defaults" extension point SHOULD be stubbed as a placeholder
node that always succeeds and logs a debug event.

Emit EV and Emit EP may have side effects; cross-reference
`docs/topics/process_models/em/` for the specific state transitions
triggered by each.

### Embargo Termination (terminate-embargo)

"other reason?" is a judgment call; stub as a placeholder. "timer expired?"
is a condition check that can be implemented as a direct comparison of the
current time against the embargo end date in the `EmbargoEvent`.

"exit embargo" is a local process placeholder for external callback hooks
(e.g., triggering advisory publication pipelines). It MUST log when
executed.

### CVE ID Assignment (assign-cve-id)

`docs/topics/behavior_logic/id_assignment_bt.md` describes a simplified
tree based on CNA rules. Implementation guidance:

- "id assigned?" — condition check; query case for existing CVE ID.
- "is CNA?" — condition check; query actor profile for CNA role.
- "in scope?" / "assignable?" — partially automatable via CNA Rules
  4.1 (<https://www.cve.org/resourcessupport/allresources/cnarules#section_4_CNA_Operational_Rules>).
  This is a candidate for an LLM-assisted evaluator: present the case
  and the relevant CNA rule text, ask the evaluator to answer a series
  of structured questions about scope and assignability.
- "emit CVE" — execution task; call CVE Services API or record a
  locally-generated placeholder ID.

### Identify Participants (identify-participants)

This is a judgment call well-suited to LLM assistance or human review:

1. Present the case information and ask an evaluator to identify potentially
   affected parties (vendors, coordinators, affected users).
2. The evaluator suggests new participants.
3. A human or policy rule reviews and confirms the suggestions.
4. For confirmed suggestions, trigger the "notify-others" flow (which uses
   `Invite(Actor, Case)` semantics — see below).

The `Suggest(Actor)` protocol message is already semantically supported,
which enables an agent workflow where a suggester-agent evaluates cases and
proposes participants, and the case owner accepts or rejects those proposals
via the normal accept/reject flow.

### Notify Others (notify-actor)

The "notify others" behavior (report to others) iterates over a list of
potential participants and sends each an `Invite(Actor, Case)` message.
Key design constraints:

1. **Embargo must be established first** (or the invitation implies
   acceptance of existing embargo terms). Before sending an `Invite`, the
   system SHOULD verify that either:
   - No embargo is active, or
   - The actor being invited is known to have compatible embargo policy
     (see `specs/embargo-policy.md`), or
   - The invitation is constructed to imply embargo acceptance upon
     acceptance of the invitation.

2. **Pre-acceptance information sharing**: Before an invited actor accepts,
   the case information shared with them SHOULD be restricted to a
   "invitation-ready" subset (see below). Full case details SHOULD only
   be shared once the invitation is accepted.

3. **Triggering**: This behavior MAY be triggered event-by-event (i.e.,
   one invitation per trigger call) rather than as a batch loop. This
   allows it to be fired immediately when a new participant is identified
   without requiring a separate batch-iteration mechanism.

4. **"effort limit exceeded?"** — stub as a placeholder that always
   succeeds (no-op for prototype); log when executed.

---

## Invitation-Ready Case Object

**Open Question**: Should `VulnerabilityCase` support a "redacted" view
for invited-but-not-yet-accepted participants? (blocks notify-actor design)

When inviting a new actor to a case under active embargo, sharing the full
case details before they have accepted the invitation creates an embargo
leak risk. A potential solution is an "invitation-ready case object" — a
stripped-down representation of the case that:

- Contains enough information for the invitee to evaluate whether to
  accept (severity, general type of vulnerability, proposed embargo terms).
- Does NOT include: full report contents, case discussion history, prior
  participant details, or any information that could identify the reporter.
- Is delivered as part of (or alongside) the `Invite` message.

Implementation options:

1. A computed property or serializer that filters `VulnerabilityCase` fields
   based on the recipient's current participation status.
2. A separate `CaseInvitationSummary` object built from `VulnerabilityCase`
   at invite time.

This is a PRIORITY 300 design item; for the prototype, the `Invite`
activity MAY reference the case by ID only, leaving the invitee to
request full details upon acceptance.

---

## Per-Participant Embargo Acceptance Tracking

**Open Question**: Should `CaseParticipant` track which embargo(es) a
participant has explicitly accepted? (blocks VP-05-* compliance)

Cases can have a series of embargoes over time (one active at a time).
If embargo terms change, participants who accepted a prior embargo may not
have accepted the new one. The current `CaseParticipant` model tracks RM
state per participant but does not explicitly track embargo acceptance.

Design options:

1. Add an `accepted_embargo_ids: list[str]` field to `CaseParticipant`
   (or `ParticipantStatus`) recording the IDs of `EmbargoEvent` objects
   the participant has explicitly accepted.
2. Derive acceptance from the protocol message history: an
   `Accept(Invite(Actor, Case))` is implicitly an acceptance of the
   current embargo; an `Accept(Offer(Embargo))` is an explicit acceptance.

**Implication for notify-others**: Before sharing case updates with a
participant, check that they have accepted the current active embargo. If
not, send a new `Offer(Embargo)` (or equivalent) before continuing. This
addresses VP-05-* items about participants signaling intent to comply
with embargoes.

This is a PRIORITY 300 item (related to `notes/do-work-behaviors.md`
"Reporting Behavior as Central Coordination").
