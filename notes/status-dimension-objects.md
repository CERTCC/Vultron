---
title: Status Dimension Objects
status: active
kind: guidance
description: >
  Rules for the per-machine dimension objects on CaseStatus and
  ParticipantStatus (ADR-0036): naming, BaseModel contract, immutable
  transition(), bare-value serialization, write-side validation, and why
  history-relative rules cannot constrain a first observation.
related_specs:
  - specs/status-dimension-objects.yaml
  - specs/architecture.yaml
  - specs/behavior-tree-node-design.yaml
related_notes:
  - notes/wire-core-boundary.md
  - notes/case-ledger-parsing.md
  - notes/lifecycle-staged-types.md
  - notes/case-state-model.md
  - notes/embargo-lifecycle.md
  - notes/message-type-reference.md
  - notes/domain-validation.md
  - notes/bt-pitfalls.md
relevant_packages:
  - vultron/core/models/case_status.py
  - vultron/core/models/participant_status.py
  - vultron/core/states/
---

# Status Dimension Objects

Each state machine on `CaseStatus` (`em`, `pxa`) and `ParticipantStatus` (`rm`,
`vf`, `d`) is a small dimension object that holds one `state` field. `pxa`,
`rm`, `vf` and `d` own their `transition()` and guard predicates; `em` has no
`transition()`, because its value is a stamped copy of the EM derived from the
embargo register (ADR-0122). Decision: ADR-0036 (split of `vfd` into
`vf` + `d`: ADR-0075). Requirements: `specs/status-dimension-objects.yaml`.

## Naming

Dimension objects take the `*Dimension` suffix (`EmDimension`, `PxaDimension`,
`RmDimension`, `VfDimension`, `DDimension`) so they do not collide with the
`VfdState` / `PxaState` NamedTuples in `vultron/core/states/cs.py`. There is no
consent dimension: participant embargo consent is per-embargo rows on
`CaseParticipant` (ADR-0122).

## BaseModel, Not CoreObject

Dimension objects are embedded value objects: no `id_`, no `Literal` `type_`, no
provenance fields. They live inside `CaseStatus` / `ParticipantStatus`, which
carry identity. Making them `CoreObject`s would bloat the schema and register
spurious vocabulary entries.

## Transitions Return a New Object

`transition(trigger)` validates the trigger and returns a **new** dimension
object; callers replace the field with `model_copy(update=...)` rather than
mutating it. This matches the append-only status history: a status record is
never mutated, a new one is appended. Prefer the dimension methods
(`rm.is_validated()`) over the free-standing `is_*()` helpers in
`vultron/core/states/`.

## A Dimension Serializes to Its Bare State Value (SDO-01-004)

`RmDimension(state=RM.START)` dumps to `"START"`; the enclosing model carries the
wire spelling as a field alias (`rm` → `rmState`). Validation accepts both the
bare value and the `{"state": ...}` mapping (SDO-01-004). There is no projection
step: a `by_alias` dump of the core object is its AS2 form (ADR-0099).

Any consumer reading a dimension out of a persisted row or ledger snapshot MUST
accept all three shapes — bare value, one-key mapping, and the flat legacy
spelling — or it silently reports `None` (#2262). Consumers:
`notes/case-ledger-parsing.md` (JSONL) and `_dimension_state` in
`vultron/adapters/driven/datalayer_sqlite/schema.py` (persistence summary).

## Write-Side Validation at BT Nodes

A dimension constructed directly by target value, not via `transition()`,
bypasses the transition contract (SDO-02-002), so the write node MUST validate
`(current → target)` before persisting:

- `target == current` → proceed (a confirmation is a valid observation).
- A legal step → proceed; otherwise `Status.FAILURE` with a `feedback_message`.
- `None` target asserts nothing about that dimension. A `None` *current* `vf`/`d`
  means the path is absent, not at its initial state (ADR-0075).

How to evaluate:

- **`ParticipantStatus` writes**: call `participant_transition_violations()`,
  normally via `validate_participant_status_write()` in
  `vultron/core/behaviors/case/nodes/participant/common.py`. It returns every
  violated rule. Calling individual predicates from a validating node violates
  BTND-10-002; `test/architecture/test_participant_status_validation.py` fails
  on it.
- **`CaseStatus` writes**: call the relevant `is_valid_*_transition()` directly.

`CreateParticipantStatusNode` is the sole `ParticipantStatus` writer
(ADR-0089) and validates the whole rule set itself, because some call sites
reach it with no upstream guard (BTND-10-003). Where a guard exists it is
fail-closed on the trigger path (`ValidateTriggerTransitionsNode`) and
partial-accept on the received path (`FilterParticipantStatusDimensionsNode` +
`ValidateRMTransitionNode`); the difference is deliberate (ADR-0061; see
[domain-validation.md](domain-validation.md)). The receive path and replica-apply
path are the only other `ParticipantStatus` write paths.
`test/architecture/test_vfd_rm_pxa_write_sites.py` fails on any new
unclassified dimension constructor call in `vultron/core/behaviors/`.

## History-Relative Rules Cannot Constrain a First Observation

- **History-free** rules (entailments, role gates) apply to any observation,
  including the first.
- **History-relative** rules (monotonicity, adjacency, regression) need a prior
  value and have nothing to compare when `current is None`.

A dimension that can be absent therefore needs one rule of each kind. Do not
manufacture a synthetic baseline (treating absence as the initial state) to make
a history-relative rule apply: it invents history the receiver does not have and
turns a legal first observation into a spurious refusal. Test for presence
(`is None`) before applying any rule that assumes a value (#2906).
