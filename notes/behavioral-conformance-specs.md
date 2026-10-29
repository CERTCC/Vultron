---
title: Behavioral Conformance Specs — Authoring Rules
status: active
kind: guidance
description: >
  Rules for writing items in the behavioral conformance spec layer (RMB, EMB,
  CSB): which sources to draft from, how a protocol shorthand trigger is traced
  through MSM, the `state_entered` precondition rule, START-state coverage for
  message-receive groups, and why not every item in a behavioral group is a
  `BehavioralSpec`.
related_specs:
  - specs/rm-behavior.yaml
  - specs/em-behavior.yaml
  - specs/cs-behavior.yaml
  - specs/vultron-protocol-spec.yaml
  - specs/meta-specifications.yaml
  - specs/message-semantics-mapping.yaml
related_notes:
  - notes/spec-authoring-rules.md
---

# Behavioral Conformance Specs — Authoring Rules

The RMB, EMB and CSB specs state, as Event-Condition-Action (ECA) rules, what a
conformant participant observably does given its state and an incoming event.
Each item links to the VP policy it implements with `rel_type: satisfies`. The
general spec-format rules (field presence decides `BehavioralSpec` versus
`StatementSpec`, ADR-0101) are in
[spec-authoring-rules.md](spec-authoring-rules.md); this note holds only the rules
specific to this layer.

## Draft from the protocol sources, in priority order

1. `docs/reference/formal_protocol/transitions.md` — organized by message type;
   informative, so where it differs from the Protocol Specification, the
   specification governs (DF-12-007).
2. `specs/vultron-protocol-spec.yaml` (VP) — the policy items to `satisfies`-link.
3. `docs/topics/behavior_logic/` diagrams — for compound conditions
   `transitions.md` does not cover; descriptive, not normative.
4. `vultron/core/behaviors/` — implementation detail; the `nodes/conditions.py`
   modules hold the precondition logic.
5. `vultron/core/case_states/patterns/potential_actions.py` — the MAY baseline.
   A MUST, SHOULD or SHOULD_NOT item downselects from the actions this table
   permits for a CS pattern; it never adds one the table forbids.

Do not draft from `vultron/bt/`: it is the legacy simulator, not the protocol
implementation.

## Cross-reference MSM for every shorthand trigger

`trigger.value` fields use protocol shorthand labels (`RS`, `EP`, `CV`, …). When
you write one, cite the matching `specs/message-semantics-mapping.yaml` (MSM)
item in the group or item description. MSM is the normative bridge from shorthand
to `MessageSemantics` value to AS2 wire form; an implementer needs that chain to
know which message the rule fires on. If MSM and the code disagree, the semantic
registry (`vultron/semantic_registry/`) shows what the code dispatches — fix
whichever is wrong.

## A `state_entered` precondition names the state just entered

In a group whose trigger is `state_entered: RM.X` (or `EM.X`, `CS.X`), each
item's `rm_state` (or `em_state`, `cs_pattern`) precondition MUST include `X`,
not the predecessor state.

**Why:** the trigger fires after the transition, so a precondition naming the
predecessor can never hold and the rule never fires. Review check: for every
`state_entered` group, confirm each item's state precondition contains the
entered state (RMB-11).

## Message-receive groups need a START-state item

A `message_received` group that covers "all states" MUST include an item for the
initial state: `RM.START` for `R*` groups (VP-03-010), `EM.NONE` for `EP`/`EA`/`EV`
groups, and the initial case-state pattern for `C*` groups.

**Why:** the START case is the one most often missed, and its required response
(for `R*`, a `Create(ProcessingFault)`, since `RE` has no wire activity) differs
from every other state's.

## Not every item in a behavioral group is a `BehavioralSpec`

RMB, EMB and CSB groups carry the trigger at group level and the ECA rule at item
level: the condition goes in typed `preconditions` (`rm_state`, `em_state`,
`cs_pattern`, `role`), and `steps` holds the action, often a single step. Bare
invariants in these groups carry none of `preconditions`, `steps` or
`postconditions`, so under ADR-0101 they load as `StatementSpec`. An
`isinstance(…, BehavioralSpec)` check over a CSB or EMB group will not match all
of it; select on field presence instead. See `specs/cs-behavior.yaml` for the
pattern.
