---
status: accepted
date: 2026-07-21
deciders: Allen D. Householder
consulted: Claude Code (design session)
---

# Per-Machine Dimension Objects for CaseStatus and ParticipantStatus

## Context and Problem Statement

`CaseStatus` and `ParticipantStatus` each pack several **independent** state
machines into flat enum fields:

- `CaseStatus.em_state: EM` — the case-level Embargo Management state
- `CaseStatus.pxa_state: CS_pxa` — the public/exploit/attack case state
- `ParticipantStatus.rm_state: RM` — the per-participant Report Management state
- `ParticipantStatus.vfd_state: CS_vfd` — the per-participant vendor fix path
- `ParticipantStatus.em_consent_state: PEC | None` — per-participant embargo consent

These machines are genuinely independent, but their transition logic is
scattered: `EmbargoLifecycle` owns EM + PEC transitions, BT nodes own
RM/vfd transitions, and neither surface expresses what *inputs* each machine
can accept or what guards apply.  Callers must know which external service
(or BT node, or inline `EMAdapter`) to call for each machine — there is no
single, self-describing owner.

The `notes/lifecycle-staged-types.md` design note and ADR-0033 both identify
this decomposition as a natural follow-on to lifecycle-staged types, with the
key observation: *staged types make illegal **shapes** unrepresentable;
dimension objects make illegal **transitions** unrepresentable.*

This ADR records the design choices made for that decomposition.

## Decision Drivers

- Give each state machine one home: the dimension object both holds state and
  owns transition validation for that machine.
- Compose naturally with the predicate/state-group model from ADR-0033: guards
  (`is_rm_validated()`, etc.) become methods on the dimension object rather than
  free-standing helpers.
- Do not proliferate identity-bearing objects — dimension objects are embedded
  value objects inside `CaseStatus`/`ParticipantStatus`, not independently
  persisted domain entities.
- Preserve DataLayer round-trip compatibility; no stored "dimension type"
  discriminator.
- Keep the wire/AS2 projection consistent: `as_CaseStatus` and
  `as_ParticipantStatus` project dimension object fields to the wire format.

## Considered Options

### Option A — Lightweight Pydantic `BaseModel` dimension objects (chosen)

Each dimension is a small Pydantic model holding one state enum and owning
an immutable `transition()` method that validates the trigger, applies the
state machine rules, and returns a new dimension object with the updated state.
Guards (`is_validated()`, `is_active()`, etc.) are additional methods.

Names:

| Object | Replaces | Embedded in |
|---|---|---|
| `EmDimension` | `CaseStatus.em_state: EM` | `CaseStatus` |
| `PxaDimension` | `CaseStatus.pxa_state: CS_pxa` | `CaseStatus` |
| `RmDimension` | `ParticipantStatus.rm_state: RM` | `ParticipantStatus` |
| `VfdDimension` | `ParticipantStatus.vfd_state: CS_vfd` | `ParticipantStatus` |
| `PecDimension` | `ParticipantStatus.em_consent_state: PEC \| None` | `ParticipantStatus` |

The naming `*Dimension` avoids collision with the existing `VfdState` and
`PxaState` NamedTuples in `vultron/core/states/cs.py`.

### Option B — Full `CoreObject` subclasses with `type_` and `CORE_VOCABULARY` entry

Dimension objects would be independently addressable domain objects with `id_`,
`type_`, and auto-registration in `CORE_VOCABULARY`.

Rejected: dimension objects are always embedded inside
`CaseStatus`/`ParticipantStatus`; there is no use case for querying or
persisting them independently.  Adding `CoreObject` overhead for embedded value
objects bloats the schema and creates unnecessary `CORE_VOCABULARY` entries.

### Option C — Property shims alongside existing flat enum fields

Add `.em`, `.rm`, etc. as computed properties returning temporary dimension
objects while keeping `em_state`, `rm_state`, etc. as the canonical fields.

Rejected: perpetuates the two-representation problem indefinitely and
produces an extended half-migrated state.

## Decision Outcome

**Chosen option: Option A — lightweight Pydantic `BaseModel` dimension objects.**

### Governing principles

1. **Lightweight BaseModel, not CoreObject** — dimension objects carry no `id_`,
   `type_`, or `CORE_VOCABULARY` entry.  They are embedded value objects owned
   by their enclosing `CaseStatus` or `ParticipantStatus`.
2. **Immutable `transition()`** — transitions return a *new* dimension object
   with the updated state; they never mutate `self`.  This is consistent with
   Pydantic's design and with the append-only history model.
3. **Replace, not alias** — flat enum fields (`em_state`, `rm_state`, etc.) are
   removed and replaced by embedded dimension object fields (`em`, `rm`, etc.).
   No shim properties.
4. **Both layers in scope** — domain model (`vultron/core/models/`) and
   wire/AS2 projection (`vultron/wire/as2/vocab/objects/case_status.py`) are
   migrated in the same implementation.
5. **Full call-site migration** — all ~308 active-codebase call sites that
   access the flat enum fields are updated.  `vultron/bt/` (legacy simulator)
   is excluded.
6. **No stored data to migrate** — there are no extant persisted records
   requiring backward-compat deserialization.

### Consequences

- **Good**: each state machine has one home; the dimension object is the
  authoritative owner of transition validation and guard predicates.
- **Good**: type signatures express which machines a function works with
  (`def accept_embargo(em: EmDimension) -> EmDimension`).
- **Good**: composable with staged types from ADR-0033 — predicates like
  `is_rm_validated()` become `rm.is_validated()` methods.
- **Neutral**: call-site migration is large (~308 sites across ~82 files in
  `vultron/` and `test/` excluding `vultron/bt/`).
- **Neutral**: the wire AS2 projection (`as_CaseStatus`, `as_ParticipantStatus`)
  must update `from_core()` / `to_core()` to handle nested dimension dicts.

## Validation

- `RmDimension.transition()` raises on an invalid trigger; returns new
  `RmDimension` with updated state on a valid one.
- `EmDimension`, `PxaDimension`, `VfdDimension`, `PecDimension` follow the
  same contract.
- `CaseStatus` / `ParticipantStatus` DataLayer round-trip: persist, `dl.read()`,
  and assert dimension objects are correctly rehydrated.
- All 308 migrated call sites pass type-checker and test suite.
- Wire round-trip: `as_CaseStatus.from_core(core_status).to_core()` produces an
  equivalent `CaseStatus` with correct dimension values.

## More Information

Related:

- ADR-0033 — Lifecycle-Staged Domain Types (predecessor; establishes the
  field-set governing principle and predicates model).
- ADR-0032 — Validate at the Edge, Promote to Strict Core Types.
- ADR-0017 — Domain/Wire Object Separation (staged types live on the core branch).
- `notes/lifecycle-staged-types.md` § "Future Direction: Per-Dimension Status
  Decomposition" — the trailhead for this decision.
- `notes/status-dimension-objects.md` — full design guidance and implementation
  notes.
- `specs/status-dimension-objects.yaml` — normative requirements (SDO-01 through SDO-04).
- #1456 — source Idea.
- #1394 — parent Epic (Architecture Hardening).
