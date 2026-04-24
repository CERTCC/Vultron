---
title: "Triggerable Behaviors: Design Notes"
status: active
description: >
  Design notes for triggerable behaviors: API endpoints, CLI commands, BT
  integration, and behavior routing patterns.
related_specs:
  - specs/triggerable-behaviors.md
  - specs/behavior-tree-integration.md
  - specs/code-style.md
related_notes:
  - notes/bt-fuzzer-nodes.md
  - notes/bt-integration.md
  - notes/do-work-behaviors.md
  - notes/domain-model-separation.md
relevant_packages:
  - transitions
---

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

The formal spec is `specs/triggerable-behaviors.md` (TRIG-01 through
TRIG-07). See `plan/IMPLEMENTATION_PLAN.md` Phase PRIORITY-30 for
implementation status.

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

**Design Decision**: The `reject-report` trigger MUST require a `note`
field (reason is required; resolved — see `specs/triggerable-behaviors.md`
TB-03-004 and `specs/code-style.md` CS-08-001).
The `note` field MUST be present; it SHOULD be non-empty. This decision
led to a broader schema-validation pattern: optional string fields
throughout the codebase follow "if present, then non-empty" (CS-08-001).

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
   binary `engage` / `defer`. In a full implementation the a full SSVC
   outcome set (e.g., *Defer*, *Scheduled*, *Out-of-Cycle*, *Immediate*, or
   others; different SSVC models have different outcome sets) MAY be
   supported.

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

**Design Decision**: `VulnerabilityCase` SHOULD support a `RedactedVulnerabilityCase`
subclass for invited-but-not-yet-accepted participants. (resolved — blocks
resolved; see `specs/case-management.md` CM-09-*)

The preferred design is:

- A `RedactedVulnerabilityCase` subclass of `VulnerabilityCase` containing
  only the fields relevant to an invitee who has not yet accepted.
- A `redact(invitee_id)` method on `VulnerabilityCase` that returns a
  `RedactedVulnerabilityCase` with appropriate fields omitted or redacted.
  Not all redactions are complete omissions — some fields may be
  partially redacted.
- Type hints enforce that redacted versions appear only where expected, and
  that a full `VulnerabilityCase` is never passed where only a redacted
  view is appropriate.
- **Opsec ID constraint**: The ID of a `RedactedVulnerabilityCase` MUST be
  completely unrelated to the full case ID. This prevents attackers who
  obtain a redacted case ID from inferring the full case ID.
- **Per-invitee unique IDs**: Each invitee MUST receive a distinct
  `RedactedVulnerabilityCase` ID so that observing one redacted ID provides
  no information about the size of the participant list or the identities
  of other invitees. (Assuming eventual encryption, this makes it very
  difficult to reconstruct the invite list.)

This is a PRIORITY 300 design item. For the prototype, the `Invite`
activity MAY reference the case by ID only, leaving the invitee to
request full details upon acceptance.

**Cross-reference**: `specs/case-management.md` CM-09-*,
`specs/encryption.md`

---

## Per-Participant Embargo Acceptance Tracking

**Design Decision**: `CaseParticipant` MUST track which embargo(es) a
participant has explicitly accepted. (resolved — see
`specs/case-management.md` CM-10-*)

Cases can have a series of embargoes over time (one active at a time).
If embargo terms change, participants who accepted a prior embargo may not
have accepted the new one. The current `CaseParticipant` model tracks RM
state per participant but does not explicitly track embargo acceptance.

Key design constraints:

- All participants MUST be on record as having accepted the active embargo
  at the time they are added to the case. This provides a complete audit
  trail of which participants were aware of which embargo terms.
- Embargo acceptances MUST be timestamped. The CaseActor applies the
  trusted timestamp (the time the CaseActor received the acceptance); the
  participant's own claimed timestamp MUST NOT be trusted for audit
  purposes.
- Design option (recommended): Add an `accepted_embargo_ids: list[str]`
  field to `CaseParticipant` (or `ParticipantStatus`) recording the IDs of
  `EmbargoEvent` objects the participant has explicitly accepted.
- An `Accept(Invite(Actor, Case))` is implicitly an acceptance of the
  current embargo; an `Accept(Offer(Embargo))` is an explicit acceptance.

**Implication for notify-others**: Before sharing case updates with a
participant, check that they have accepted the current active embargo. If
not, send a new `Offer(Embargo)` (or equivalent) before continuing. This
addresses VP-05-* items about participants signaling intent to comply
with embargoes.

This is a PRIORITY 300 item (related to `notes/do-work-behaviors.md`
"Reporting Behavior as Central Coordination").

---

## Resolved Design Decisions: Trigger Implementation (P30-1 through P30-3)

These decisions were reached during initial implementation of the trigger
endpoints in `vultron/api/v2/routers/triggers.py`.

### P30-1: Outbox Diff Strategy for Retrieving the Resulting Activity

`trigger_validate_report` (and similar BT-backed triggers) needs to return
the resulting ActivityStreams activity in the response body (TRIG-04-001).
The BT writes the new activity ID to `actor.outbox.items` via the
`UpdateActorOutbox` node.

**Design decision**: Snapshot the actor's outbox ID set before BT execution,
then subtract after execution to find newly added activity IDs. The diff is a
set subtraction on string IDs.

**Rationale**: Avoids modifying the bridge layer or BT nodes for a specific
trigger use case. Concurrency-safe as long as each BT execution produces a
distinct UUID-based activity ID (guaranteed by existing BT node
implementations).

**Implication**: This approach couples the trigger endpoint to the outbox
data model. If the outbox model changes (e.g., moving to a separate outbox
collection), the snapshot/diff logic must also be updated.

### P30-2: Report Triggers are Procedural (invalidate-report, reject-report)

`invalidate-report` and `reject-report` are implemented procedurally, not
as BT trees. Per AGENTS.md guidance, simple linear workflows with no
branching SHOULD use procedural code.

- `invalidate-report`: Creates `RmInvalidateReport` (TentativeReject) directly.
- `reject-report`: Creates `RmCloseReport` (Reject) directly; requires a
  non-empty `note` field (TRIG-03-004).

**Shared helper**: `_add_activity_to_outbox()` was extracted to DRY up the
outbox-append pattern across multiple trigger endpoints (avoids repeating the
same DataLayer read → append → write sequence).

**`reject-report` `note` field semantics**: The spec says the value SHOULD be
non-empty (not MUST). An empty `note` string logs a WARNING but is accepted.
This is enforced via a `@field_validator` on `RejectReportRequest.note` rather
than a `NonEmptyString` type, because the rule is advisory (SHOULD), not
mandatory (MUST).

### P30-3: Case Triggers are Procedural (engage-case, defer-case)

`engage-case` and `defer-case` are also implemented procedurally. Key pattern
differences from report triggers:

- **`_resolve_case()` helper**: Reads the case from the DataLayer and returns
  HTTP 404 if absent or HTTP 422 if the resolved object is not a
  `VulnerabilityCase`. Shared across case-scoped trigger endpoints.
- **`_update_participant_rm_state()` helper**: Locates the actor's own
  `CaseParticipant` record in the DataLayer (participants are stored as ID
  strings in `case.case_participants`, so each must be fetched individually)
  and updates `participant_statuses`. If no participant record exists for the
  actor, a WARNING is logged and the endpoint still returns 202 (non-blocking).
- **State update target**: The participant document is updated directly, not
  the case document, consistent with existing BT node patterns.
- **Relationship to receive-side BTs**: `EngageCaseBT`/`DeferCaseBT` handle
  the *inbound* case — recording another actor's already-made decision.
  The trigger endpoints handle the *outbound* case — the local actor deciding
  to engage or defer. The `EvaluateCasePriority` BT node is
  **outgoing-only** and does NOT appear in the receive-side trees.

### Request Model DRY Pattern

When implementing trigger request models, check existing models first:

- `ValidateReportRequest` and `InvalidateReportRequest` are identical;
  prefer a shared base class over two independent models.
- `RejectReportRequest` extends the base by adding a required `note` field.
- All request models SHOULD use `model_config = ConfigDict(extra="ignore")`
  for forward-compatibility (TRIG-03-002).

**See also**: `specs/triggerable-behaviors.md`.

---

## BT Requirement for Trigger Use Cases

Trigger use cases follow the same BT requirement as received use cases:
all protocol-observable behaviors MUST be implemented as BT nodes or
subtrees. A trigger endpoint's `execute()` method is permitted to contain
infrastructure glue (build event, set up blackboard), but the domain logic
MUST live in the BT.

In particular, trigger use cases MUST NOT call `SvcXxxUseCase().execute()`
or equivalent domain functions procedurally after `bridge.execute_with_setup()`
returns. Cascades from the triggering action to downstream protocol behaviors
must be expressed as BT child subtrees.

See `specs/behavior-tree-integration.md` BT-06-005 and BT-06-006, and
`notes/bt-integration.md` for the subtree composition model (see "Canonical CVD
Protocol Behavior Tree Reference" section).
