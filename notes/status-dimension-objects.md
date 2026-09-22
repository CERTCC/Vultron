---
title: Status Dimension Objects
status: active
description: >
  Design guidance for per-machine dimension objects decomposed from CaseStatus
  and ParticipantStatus: naming, BaseModel contract, immutable transition()
  pattern, wire projection, and call-site migration scope.
related_specs:
  - specs/status-dimension-objects.yaml
  - specs/architecture.yaml
related_notes:
  - notes/wire-core-boundary.md
  - notes/case-ledger-parsing.md
  - notes/lifecycle-staged-types.md
  - notes/case-state-model.md
  - notes/embargo-lifecycle.md
  - notes/message-type-reference.md
relevant_packages:
  - vultron/core/models/case_status.py
  - vultron/core/models/participant_status.py
  - vultron/core/states/
  - vultron/wire/as2/vocab/objects/case_status.py
---

# Status Dimension Objects

Design note for ADR-0036. Records *why* the dimension-object design is shaped
the way it is; the normative requirements live in
`specs/status-dimension-objects.yaml` (SDO-01 through SDO-04), and the
decision record is `docs/adr/0036-status-dimension-objects.md`.

This is the natural follow-on to ADR-0033 (Lifecycle-Staged Domain Types):
staged types make illegal *shapes* unrepresentable; dimension objects make
illegal *transitions* unrepresentable.

---

## The Problem

`CaseStatus` and `ParticipantStatus` pack several independent state machines
into flat enum fields:

```python
# CaseStatus (before)
em_state: EM = EM.NONE
pxa_state: CS_pxa = CS_pxa.pxa

# ParticipantStatus (before)
rm_state: RM = RM.START
vfd_state: CS_vfd = CS_vfd.vfd
em_consent_state: PEC | None = None
```

These machines are genuinely independent, but callers must know:

- *which external service* handles each transition (EM + PEC → `EmbargoLifecycle`;
  RM/vfd → BT nodes or `EmbargoLifecycle` indirectly; PXA → BT lifecycle nodes).
- *which guards apply* before calling (P/X/A embargo-eligibility checks, RM
  terminal guards, etc.).

There is no single, self-describing owner per machine. Bugs fixed in
`EmbargoLifecycle` do not automatically close gaps in BT nodes that
independently mutate `em_state`.

---

## The Solution: Dimension Objects

Decompose each machine into a small Pydantic `BaseModel` — a *dimension object*
— that holds one state enum field and owns:

- An immutable `transition(trigger)` method that validates the trigger,
  applies the machine rules, and returns a **new** dimension object.
- Guard predicates as methods (`is_validated()`, `is_active()`, etc.).

```python
# CaseStatus (after)
em: EmDimension = Field(default_factory=EmDimension)
pxa: PxaDimension = Field(default_factory=PxaDimension)

# ParticipantStatus (after — ADR-0036 original; ADR-0075 then split vfd into vf+d)
rm: RmDimension = Field(default_factory=RmDimension)
vf: VfDimension | None = None   # non-None for VENDOR participants
d: DDimension | None = None     # non-None for DEPLOYER participants
consent: PecDimension | None = None
```

---

## Naming

| Dimension object | State enum | Replaces |
|---|---|---|
| `EmDimension` | `EM` | `CaseStatus.em_state` |
| `PxaDimension` | `CS_pxa` | `CaseStatus.pxa_state` |
| `RmDimension` | `RM` | `ParticipantStatus.rm_state` |
| `VfDimension` | `CS_vf` | `ParticipantStatus.vf` (VENDOR participants; ADR-0075) |
| `DDimension` | `CS_d` | `ParticipantStatus.d` (DEPLOYER participants; ADR-0075) |
| `VfdDimension` | `CS_vfd` | retained in `vultron/bt/` legacy only; use `VfDimension`/`DDimension` in new code |
| `PecDimension` | `PEC` | `ParticipantStatus.em_consent_state` |

The `*Dimension` suffix was chosen to avoid collision with the existing
`VfdState` and `PxaState` NamedTuples in `vultron/core/states/cs.py`.

---

## BaseModel, not CoreObject

Dimension objects are **embedded value objects**. They do NOT have:

- `id_` (no independent identity)
- `type_` with a Literal value (no CORE_VOCABULARY registration)
- `published`, `updated`, `attributed_to` (no provenance metadata)

They are always embedded inside `CaseStatus` or `ParticipantStatus`, which
already carry identity. Adding `CoreObject` overhead would bloat the schema
and create spurious CORE_VOCABULARY entries.

---

## Immutable transition() Pattern

```python
class RmDimension(BaseModel):
    state: RM = RM.START

    def transition(self, trigger: RM_Trigger) -> "RmDimension":
        """Return a new RmDimension with the updated state.

        Raises VultronInvalidStateTransitionError if the trigger is invalid
        for the current state.
        """
        next_state = _apply_rm_transition(self.state, trigger)
        return self.model_copy(update={"state": next_state})

    def is_validated(self) -> bool:
        return self.state in RM_VALIDATED

    def is_active(self) -> bool:
        return self.state in RM_ACTIVE
```

Callers replace the field rather than mutating in place:

```python
# Before (mutable, brittle)
participant_status.rm_state = RM.VALID

# After (immutable, explicit)
participant_status = participant_status.model_copy(
    update={"rm": participant_status.rm.transition(RM_Trigger.VALIDATE)}
)
```

This is consistent with the append-only history model: a status record is
never mutated; a new record is appended with the updated dimension values.

---

## Wire Projection

> **Superseded by [ADR-0099](../docs/adr/0099-one-object-model-as2-is-a-serialization.md)
> (detail 5, SDO-01-004).** This section previously recommended matching the wire
> JSON shape to the nested dimension structure, and routing projection through the
> ADR-0082 pairing registry and adapter-side translator. Both recommendations are
> cancelled. The rest of this note — the naming table, the `BaseModel`-not-`CoreObject`
> rationale, the immutable `transition()` pattern and the call-site migration
> scope — still stands.

**A dimension object serializes to its bare state value, not to a one-key
mapping.** `RmDimension(state=RM.START).model_dump(mode="json")` is `"START"`, and
the enclosing model carries the wire spelling as a field alias — `rm` with
`serialization_alias="rmState"` — so the serialized result is `{"rmState": "START"}`
(SDO-01-004).

The reasoning: a dimension holds exactly one data field, `state`. Everything else
on it is behaviour, and behaviour does not serialize, so the one-key wrapper was
putting a container on the wire whose only content was the thing it contained.

**Both input forms are accepted.** `RmDimension.model_validate("ACCEPTED")` and
`RmDimension.model_validate({"state": "ACCEPTED"})` both succeed, so callers that
construct the mapping form keep working and rows stored either way rehydrate
(SDO-06-001).

Two consequences worth carrying:

- Because the core class now declares the AS2 aliases itself, core
  `ParticipantStatus` emits the same AS2 payload as `as_ParticipantStatus` — which
  is what lets the wire form stay unchanged while the paired class is deleted.
- **Any consumer that reads a dimension out of a persisted row or a ledger
  snapshot must accept all three shapes** — bare value, one-key mapping, and the
  flat legacy `rmState` spelling. `notes/case-ledger-parsing.md` covers the
  JSONL-consumer side; `_dimension_state` in
  `vultron/adapters/driven/datalayer_sqlite/schema.py` is the persistence-summary
  side. A reader that handles only the older two silently reports `None`, which is
  the issue #2262 / #2232 failure shape.

Projection still lives on the wire classes (`from_core` / `to_core`) for now.
ADR-0099 supersedes ARCH-12-005's relocation of it: there is no pairing registry
and no adapter-side translator to move it to, because the second hierarchy is being
removed rather than reconciled. See
[notes/wire-core-boundary.md](wire-core-boundary.md).

---

## Relationship to Existing Predicates

The existing state-group tuples and `is_*()` free-standing helpers in
`vultron/core/states/` continue to work; they accept the raw enum values that
dimension objects hold. Over time, callers should prefer the dimension-object
methods (`rm.is_validated()`) over the free-standing helpers
(`is_rm_validated(status.rm_state)`).

---

## Write-Side Validation at BT Nodes

Dimension objects that are constructed directly by target state value
(e.g. `VfdDimension(state=target)`) rather than via `transition()` **bypass
the transition contract** in SDO-02-002. BT write nodes that use this pattern
MUST validate the `(current → target)` pair before persisting.

The rules a write must satisfy are the same in every case:

- `target == current` → proceed (status confirmation; valid protocol observation)
- The `(current → target)` step is legal → proceed
- Otherwise → `Status.FAILURE` with a descriptive `feedback_message`
- `None` target → asserts nothing about that dimension; no per-dimension rule
  applies. Note that a `None` *current* `vf`/`d` means the dimension is
  **absent**, not at its initial state (ADR-0075)

What differs is **how** a node evaluates them, and for `ParticipantStatus` that
changed with ADR-0086:

- **`ParticipantStatus` writes**: call `participant_transition_violations()`
  (`vultron/core/states/participant_transitions.py`), normally through
  `validate_participant_status_write()` in
  `behaviors/case/nodes/participant/common.py`. It composes the per-dimension
  transitions, the VENDOR/DEPLOYER role gates, the cross-machine entailments and
  the compound CS transition, and returns **every** violated rule. Calling the
  individual `is_valid_*_transition()` / `violation_*` predicates from a
  validating node is a BTND-10-002 violation and
  `test/architecture/test_participant_status_validation.py` fails on it.
- **`CaseStatus` and other dimension writes**: call the relevant
  `is_valid_*_transition()` helper from `vultron/core/states/` directly.

The ideal is for write nodes to be fail-closed regardless of whether an upstream
guard is present, weak, or bypassed. See BTND-10-001, BTND-10-003, SDO-02-004,
CSB-16-001/002.

The primary write boundary is `CreateParticipantStatusNode` in
`vultron/core/behaviors/case/nodes/participant/status.py` — all VFD/RM/PXA
state-write paths in the prototype route through it, and since ADR-0086 it
validates the **whole** rule set itself rather than trusting an upstream guard
(BTND-10-003). Five production call sites reach it without any guard, so its own
check is the only validation on those paths. Where a guard *is* present it
enforces the same composed rule set:

- **Trigger path**: `ValidateTriggerTransitionsNode` — fail-closed; reports every
  violation and fails the enclosing `Sequence` before the write node ticks, so the
  two do not double-report.
- **Received wire path**: `FilterParticipantStatusDimensionsNode` +
  `ValidateRMTransitionNode` — partial-accept; refused dimensions carry the
  current value forward. The opposite disposition from the trigger path, on
  purpose: Postel's maxim, not an inconsistency (ADR-0061, ADR-0086). See
  [notes/domain-validation.md](domain-validation.md).

`CreateParticipantStatusNode` is now the sole `ParticipantStatus` writer
(ADR-0089, closing #3111): the model-level `append_rm_state` mutators were
removed and pre-case RM state moved onto `VultronReportCaseLink`
(`_ReportPhaseRMTransition` writes the link's `rm_state`, not a
`ParticipantStatus`). The only two `ParticipantStatus`-write exclusions that
remain are the receive path and the replica-apply path, which adjudicate under a
different disposition by design.

`test/architecture/test_vfd_rm_pxa_write_sites.py` (the AC-7 ratchet) AST-scans
`vultron/core/behaviors/` for every dimension constructor call and fails on any
new unclassified site, making it hard to add an unguarded write path silently.

---

## History-Relative Rules Cannot Constrain a First Observation

When adjudicating a dimension value, separate the rules into two kinds:

- **History-free** rules — entailments and role gates — depend only on the value
  and the participant's structure. They apply to *any* observation, including the
  first.
- **History-relative** rules — monotonicity, adjacency, regression — compare the
  incoming value against a prior one. They have nothing to bite on when there is
  no prior value (`current is None`): a first observation cannot "regress" from a
  state the receiver never held.

So a dimension that can legitimately be absent needs **one rule of each kind** —
a history-free rule to constrain the first observation and a history-relative
rule to constrain subsequent ones. Do **not** manufacture a synthetic baseline
(e.g. treating absence as the enum's initial state) just to make a
history-relative rule apply: that invents history the receiver does not have and
turns a legal first observation into a spurious refusal.

**Corollary — absence is structural, not initial.** An absent `vf`/`d` dimension
means the participant has no vendor/deployer path at all under ADR-0075, not that
the dimension sits at its initial value. Reading a missing `CS_vf.vf` as the
initial state produces bogus VF↔D entailment refusals. Test the dimension object
for *presence* (`is None`) before applying any rule that assumes a value.

The concrete VF/D adjudication rules that follow from this are already captured
in `_adjudicate_vf`'s docstring and in spec RSH-05-020's note; this card records
only the general principle so it transfers to any absent-capable dimension. See
[[bt-pitfalls]] § write-side validation and [[case-state-model]].

Source: ISSUE-2906
