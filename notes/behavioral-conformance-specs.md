---
title: Behavioral Conformance Specs — Design Decisions
status: active
description: >
  Design rationale and implementation plan for the behavioral conformance spec
  layer (RMB, EMB, CSB): ECA rules, schema extensions, and the relationship
  between protocol policy (VP) and behavioral requirements.
related_specs:
  - specs/vultron-protocol-spec.yaml
  - specs/meta-specifications.yaml
  - specs/spec-registry.yaml
  - specs/message-semantics-mapping.yaml
related_notes:
  - notes/specs-vs-adrs.md
  - notes/bt-integration.md
  - notes/protocol-event-cascades.md
  - notes/event-driven-control-flow.md
---

# Behavioral Conformance Specs — Design Decisions

## Problem Statement

A large part of the Vultron protocol's behavior logic is currently embodied in
the py_trees behavior trees in `vultron/core/behaviors/`, and described
(descriptively, without normative language) in `docs/topics/behavior_logic/`.
An independent implementor — one who wants to build a Vultron-compliant system
without using this codebase as a template — has no machine-readable,
normatively-phrased specification of what their system must *do* in response to
protocol events and state conditions.

The existing `specs/vultron-protocol-spec.yaml` (VP) captures *policy* ("what
must be true"), and `docs/reference/formal_protocol/transitions.md` captures
normative message-level rules, but neither is organized as Event-Condition-Action
(ECA) rules. The behavior logic docs are purely descriptive and explicitly
frame BTs as *one* implementation approach, not a requirement.

## Core Insight: SHOULD/MUST Are a Downselect on MAY

The existing `vultron/core/case_states/patterns/potential_actions.py` already
encodes a MAY table: given a 6-char CVD state pattern, what actions are
*permitted*. The behavioral conformance specs add the normative layer on top:
of the permitted actions, which ones are MUST, SHOULD, or SHOULD_NOT under
what triggering conditions.

## Conformance Level Framing

Three levels an independent implementor can achieve:

- **L1 — Syntax**: well-formed messages (covered by wire format specs)
- **L2 — Semantic**: correct state transitions per message (covered by VP +
  transitions.md)
- **L3 — Behavioral**: correct observable outputs — right messages emitted,
  right states reached, given (input state + received message/event). This is
  what the new RMB/EMB/CSB specs cover.

A fourth level (L4 — Process: correct internal decision structure, e.g.,
precondition before state write before effect) is enforceable only via a
reference implementation. Some process ordering also rises to L3 when the
sequence of outputs is itself observable. For example, CP-before-ET (when
public disclosure triggers embargo teardown) is now normatively specified in
CSB-12-001 as a MUST, not just an implementation convention.

## Why New Files, Not VP Extensions

VP's items are flat normative statements: "Participants MUST X." ECA rules have
a three-part shape (precondition + trigger + required response) that doesn't
compress cleanly into that pattern. Adding 50+ ECA rules to VP would mix two
structurally different item kinds in one file and make VP hard to navigate.

New files also allow independent versioning. VP is already v1.0.0; the
behavioral layer starts at v0.1.0 and can stabilize separately.

The relationship direction: RMB/EMB/CSB items carry
`relationships: [{rel_type: satisfies, spec_id: VP-XX-XXX}]` pointing to the
VP policy they implement. Reverse traversal is free via
`SpecRegistry.graph` (networkx DiGraph, use `.predecessors(vp_id)`).

## Key Ordering Constraints Captured

Some ECA rules are not just "do A when B" but "do A *before* B." These use
`steps:` on `BehavioralSpec` items to encode ordering. Critical ones:

- **CS→P triggers embargo teardown** (CSB-12-001, CSB-04-003): record CS state
  transition *first*, then initiate teardown. Observable: CP must precede ET in
  the message stream. This is normatively specified as MUST and is also enforced
  structurally in `add_case_status_tree` (AppendCaseStatusToCaseNode runs before
  ThreatTerminationBranchNode).
- **Ephemeral states: pX→PX invariant** (CSB-13-001, CSB-17-003, CSB-17-012):
  when the CS PXA state is pXa or pXA (exploit public without public awareness),
  the next CS event MUST be P. **Write-boundary enforcement** (AC-1, PR #2479):
  `_promote_pxa()` in `AppendCaseStatusToCaseNode` and `EmitCaseStatusUpdateNode`,
  and `_apply_ac1_promotions()` in `CreateParticipantStatusNode`, prevent
  pXa/pXA from being persisted. **Receive-path enforcement** (PR #2888):
  `CheckCsEphemeralStateNode` in `add_case_status_tree` returns FAILURE if
  asserted PXA does not advance P from a pX state. See #2524, PR #2888.
- **CS history validity** (CSB-17-004, CSB-17-005): complete CS histories must
  be one of 70 valid histories; incomplete histories must be valid prefixes.
  Enforced in `add_case_status_tree` via `CheckCsHistoryPrefixNode` (precondition
  guard, rejects single-event PXA transitions that produce an invalid prefix).
  Multi-event advances and PXA regressions are deferred to
  `FilterCsPxaDimensionNode` (RSH-05). See #2524, PR #2888.
- **Ledger commit ordering** (from `specs/case-ledger-processing.yaml`
  CLP-10-006): precondition checks → ledger commit → protocol effects.
  Observable from audit replay.
- **CX in state `...px.`**: emitting CX must also trigger CS→P and emit CP.
  Observable: CX without CP from a sender in `...px.` is a detectable violation.
- **RS in EM Proposed = implicit EA**: VP-06-007 (SHALL). Observable: RS after
  EP without explicit EA is treated as acceptance by the sender.

## Relationship to Behavior Logic Docs

`docs/topics/behavior_logic/` docs are known to be out of sync with the
implementation and contain no normative language. They should NOT be the
primary home for requirements.

After the specs are written:

- Each behavior logic doc gets a "Requirements" section at the top listing
  relevant RMB/EMB/CSB spec IDs.
- BT diagrams are demoted to "Implementation approach" sidebars with a note
  that they illustrate one conformant implementation.
- `docs/reference/formal_protocol/transitions.md` gets inline spec ID citations.
- `docs/howto/general_implementation.md` gets a conformance levels section
  (L1/L2/L3/L4).

Docs are updated *after* specs are stable, so doc cross-references point to
stable IDs.

## Primary Sources for Spec Content

When drafting spec item content, use these sources in priority order:

1. `docs/reference/formal_protocol/transitions.md` — already normative,
   organized by message type
2. `specs/vultron-protocol-spec.yaml` (VP) — existing normative items to
   `satisfies`-link from
3. `docs/topics/behavior_logic/` BT diagrams — for compound conditions not in
   transitions.md; treat as descriptive ground truth for current intent
4. `vultron/core/behaviors/` py_trees code — for implementation details;
   focus on `nodes/conditions.py` files for precondition logic
5. `vultron/core/case_states/patterns/potential_actions.py` — for MAY baseline
   (the permitted action set that SHOULD/MUST downselects from)

Do NOT use `vultron/bt/` (legacy simulator) as a source. Focus exclusively on
the `vultron/core/behaviors/` py_trees layer.

## Protocol Shorthand → MessageSemantics → VAM Traceability

RMB/EMB/CSB `trigger.value` fields use protocol shorthand labels (RS, EP, EA,
CV, CP, etc.). An independent implementor needs a normative document that
bridges these shorthands to the implementation:

1. **Shorthand label** (e.g., `EP`) — used in behavioral spec trigger values
   and VP spec prose
2. **`MessageSemantics` enum value** (e.g., `INVITE_TO_EMBARGO_ON_CASE`) — the
   domain-layer semantic intent used for dispatch
3. **VAM spec item ID** (e.g., `VAM-05-005`) — the wire-format mapping

This three-hop chain is captured normatively in
`specs/message-semantics-mapping.yaml` (MSM prefix).
Each MSM item provides one row in the flat table:
shorthand → MessageSemantics → VAM ID.

**Authoring rule for behavioral specs**: when writing a `trigger.value` field
with a protocol shorthand label, always cross-reference the corresponding MSM
spec item in the group or item description. The extractor code
(`vultron/wire/as2/extractor/_instances.py`) is the authoritative source if
the shorthand→MessageSemantics mapping differs between the code, legacy
ontology, and docs.

## Authoring Pitfalls

### `state_entered` Trigger vs. Precondition Mismatch

(ISSUE-1424, 2026-07-15)

When writing `BehavioralSpec` items inside a group whose `trigger` is
`state_entered: RM.X` (or `EM.X`, `CS.X`), the item's `rm_state`
precondition MUST list the state that was just *entered* — not the
predecessor state.

```yaml
# ✅ CORRECT — state_entered: RM.INVALID means we are now IN RM.INVALID
- id: RMB-11-002
  preconditions:
  - rm_state: [RM.INVALID]   # the state just entered

# ❌ WRONG — RM.RECEIVED is the state *before* the transition
- id: RMB-11-002
  preconditions:
  - rm_state: [RM.RECEIVED]  # impossible: we are no longer in RECEIVED
```

**Why it matters**: A `state_entered: RM.X` group's trigger fires *after*
the transition, so any precondition must be satisfiable *in* the new state.
A precondition requiring a predecessor state is structurally unreachable —
the behavior can never execute.

**Review checklist**: For every `state_entered: RM.X` group, grep all
items' `rm_state` preconditions and verify each contains `X`.

---

### START-State Variants Required for Message-Receive Groups

(ISSUE-1424, 2026-07-15)

Per VP-03-010, message-receive groups covering "all states" MUST include
a START-state variant (e.g., `RMB-07` for `R*` messages must have an item
with `rm_state: [RM.START]`). Code review on `specs/rm-behavior.yaml`
found `RMB-07` and `RMB-08` missing their START-state items while
`RMB-02` through `RMB-06` each had one.

**Pattern**: For any `message_received: R*` group, systematically audit
whether `RM.START` is covered. The same rule applies to `EP` / `EA` /
`EV` groups for `EM.NONE` and to `C*` message groups for the initial
case-state pattern.

---

### Intent Over Letter: When Spec Text and Issue Body Conflict

(ISSUE-1272, 2026-07-10)

When a spec entry and its associated GitHub issue body conflict with each
other, or when either conflicts with established architectural principles,
implement the **observable intent** — what the system must *do from the
outside* — then **correct the spec entry** in the same PR rather than
silently complying with a stale requirement.

Specifically:

- If the spec mechanism (e.g. "MUST NOT invoke `create_receive_report_case_tree`")
  contradicts the architectural pattern (BT-first, thin use-cases), reword
  the spec to describe the outcome, not the mechanism.
- If the issue body contains a factual error about the codebase (e.g., "the
  BT already has access to ActorConfig through the blackboard" when it actually
  threads via constructor arg), note the correction in a PR comment and implement
  the correct path.
- Use `AskUserQuestion` to surface genuine design forks — divergences where
  both interpretations are architecturally valid.

Neither specs nor issue text constrain the *right* solution; they steer
away from bad ones. The spec is authoritative once corrected; the issue
text is ephemeral.

Also: **BT gate placement matters.** The idempotency idiom
`Selector(Sequence(guard, work), Success)` **masks** downstream FAILURE.
When a downstream FAILURE must still propagate (e.g., case creation can
genuinely fail), use `Sequence[gate, existing_Selector]` instead so the
gate fails-safe without swallowing real failures.

---

## StatementSpec vs BehavioralSpec Selection

Use the MS-13 decision tree (from `specs/meta-specifications.yaml`) when choosing
between `StatementSpec` and `BehavioralSpec` for a spec item:

- **Use `BehavioralSpec`** when the item describes a **sequential, stateful process**
  with a defined start state, ordered actions, and terminal conditions — e.g., a demo
  scenario workflow, a received-message handler sequence, or a multi-step handshake.
- **Use `StatementSpec`** when the item expresses a capability constraint, behavioral
  property, or structural rule where step ordering is not part of the requirement.

A common anti-pattern: embedding numbered sub-steps inside a `StatementSpec` statement
field (e.g., `M1 (…), M2 (…), M3 (…)` milestone lists, or `(1) do A; (2) do B` handler
sequences). This violates MS-05-001 (no inline prose explanations) and hides start
states, ordering, and terminal conditions from conformance tooling. Extract those steps
into `BehavioralSpec.steps[]` instead.

### Demo scenario groups

Demo scenario workflow groups (e.g., `DEMOMA-06`, `-09`, `-10`, `-11`) follow the
`BehavioralSpec` pattern established in `DEMOMA-12`. The group carries
`trigger: {type: scenario_start, value: <scenario-name>}` (per MS-13-003). Individual
items describing ordered protocol exchanges use `BehavioralSpec`; items expressing
terminal-state requirements or infrastructure constraints (`MUST reach final state X`,
`MUST add a CI job`) remain `StatementSpec`.

Since MS-13-004 (CONCERN-1650), `spec-lint` hard-errors when a `scenario_start`
group contains no `BehavioralSpec` item with non-empty `steps`. The
`.github/workflows/spec-check.yml` CI workflow enforces this on every `specs/**`
change. New scenario spec authors should ensure at least one `BehavioralSpec`
item with a non-empty `steps` list is present, or the spec-lint CI check will
fail.

### Protocol behavioral groups

Protocol behavioral groups (RMB, EMB, CSB) always use `BehavioralSpec`. See the
`cs-behavior.yaml` reference for the trigger-at-group / ECA-at-item pattern with
typed `Precondition` fields (`rm_state`, `em_state`, `cs_pattern`, `role`).

---
