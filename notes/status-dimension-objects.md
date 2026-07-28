---
title: Status Dimension Objects
status: active
description: >
  Design guidance for per-machine dimension objects decomposed from CaseStatus
  and ParticipantStatus: naming, BaseModel contract, immutable transition()
  pattern, wire projection, and call-site migration scope.
related_specs:
  - specs/status-dimension-objects.yaml
related_notes:
  - notes/lifecycle-staged-types.md
  - notes/case-state-model.md
  - notes/embargo-lifecycle.md
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
em_state: EM = EM.NO_EMBARGO
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

# ParticipantStatus (after)
rm: RmDimension = Field(default_factory=RmDimension)
vfd: VfdDimension = Field(default_factory=VfdDimension)
consent: PecDimension | None = None
```

---

## Naming

| Dimension object | State enum | Replaces |
|---|---|---|
| `EmDimension` | `EM` | `CaseStatus.em_state` |
| `PxaDimension` | `CS_pxa` | `CaseStatus.pxa_state` |
| `RmDimension` | `RM` | `ParticipantStatus.rm_state` |
| `VfdDimension` | `CS_vfd` | `ParticipantStatus.vfd_state` |
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

`as_CaseStatus` and `as_ParticipantStatus` project dimension objects to the
wire format. The `from_core()` / `to_core()` methods must handle the nested
dimension-object dict shape:

```python
# from_core() — core dimension objects → wire flat fields (for backward wire compat)
# OR — wire flat fields remain nested dicts (simpler, no backward wire compat needed
#       since there are no extant records to preserve)
```

Because there are no extant persisted records to preserve, the simplest
approach is to match the wire JSON shape to the new nested structure and
update `from_core()` / `to_core()` accordingly.

---

## Call-Site Migration Scope

There are approximately 308 call sites in `vultron/` and `test/` (excluding
`vultron/bt/`) that access the old flat enum fields. The migration pattern
is mechanical:

| Old access pattern | New access pattern |
|---|---|
| `status.em_state` | `status.em.state` |
| `status.pxa_state` | `status.pxa.state` |
| `status.rm_state` | `status.rm.state` |
| `status.vfd_state` | `status.vfd.state` |
| `status.em_consent_state` | `status.consent.state` (or `None` check) |
| `CaseStatus(em_state=EM.ACTIVE, ...)` | `CaseStatus(em=EmDimension(state=EM.ACTIVE), ...)` |

The `vultron/bt/` legacy simulator is **out of scope** — it uses the custom
BT engine and accesses enums directly; migrating it is a separate effort.

---

## Relationship to Existing Predicates

The existing state-group tuples and `is_*()` free-standing helpers in
`vultron/core/states/` continue to work; they accept the raw enum values that
dimension objects hold. Over time, callers should prefer the dimension-object
methods (`rm.is_validated()`) over the free-standing helpers
(`is_rm_validated(status.rm_state)`).

---

## Relationship to EmbargoLifecycle

`EmbargoLifecycle` currently mutates `em_state` and `em_consent_state` fields
directly on `CaseStatus`/`ParticipantStatus`. After this migration, it MUST
use the dimension-object transition pattern:

```python
# Before
case_status.em_state = new_em_state

# After
updated_em = EmDimension(state=new_em_state)
# ... or via transition():
updated_em = case_status.em.transition(EM_Trigger.ACTIVATE)
case_status = case_status.model_copy(update={"em": updated_em})
```

This is the single most complex migration site (`embargo_lifecycle.py` has
~17 flat-field accesses). The impl agent should prioritize this file.
