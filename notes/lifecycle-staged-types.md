---
title: Lifecycle-Staged Domain Types
status: active
description: >
  Design guidance for lifecycle-staged domain types anchored on guaranteed-field
  changes: the field-set governing principle, the three-class analysis, the
  model_validate-at-edge read mechanism, the data-as-source-of-truth transition
  model, and the DataLayer round-trip constraint.
related_specs:
  - specs/lifecycle-staged-types.yaml
  - specs/architecture.yaml
related_notes:
  - notes/domain-model-separation.md
  - notes/domain-validation.md
  - notes/case-state-model.md
relevant_packages:
  - vultron/core/models
  - vultron/core/states
---

# Lifecycle-Staged Domain Types

Design note for ADR-0033. Records *why* the staged-type design is shaped the way
it is; the normative requirements live in `specs/lifecycle-staged-types.yaml`
(LST-01 through LST-05), and the decision record is
`docs/adr/0033-lifecycle-staged-case-types.md`.

## The Problem

`VulnerabilityCase` is the "fat class" named in ADR-0032: one type for a case at
every lifecycle stage. Core functions that need a case to have reached a stage
(e.g. "there is an active embargo") cannot say so in their signatures and fall
back on runtime guards (`if case.active_embargo is None`,
`case.current_status.em_state == EM.ACTIVE`).

Note that the *current* `VulnerabilityCase` has almost no literal `X | None`
fields — only `active_embargo`; its collections already default to empty. The
real problem is not annotation noise but that **one class represents a case at
every stage**, so functions cannot type-demand a stage.

## The Governing Principle

> A lifecycle milestone earns a distinct staged **type** only when it changes
> the set of guaranteed (required, non-None) fields. A milestone that only
> changes *which actions are permitted* — without changing which fields are
> present — belongs in the transition model and precondition specs, not the
> type hierarchy.

This single rule resolves every tension below and prevents type proliferation
(the P/X/A dimensions alone would otherwise imply 2³ combinations).

## Three-Class Analysis

The domain has three state-bearing classes. Applying the principle to each:

### VulnerabilityCase — case-universal facts (earns types)

RM state is **per-participant**, so "the case is valid/accepted" is undefined
(valid according to whom?). Only these facts are case-universal and monotonic:

| Milestone | Adds a guaranteed field? | Result |
|---|---|---|
| Case exists (ADR-0015 create-on-receipt) | Yes — participants, reports, seeded status | **`Case` type** |
| Embargo active (`em_state ∈ {ACTIVE, REVISE}`) | Yes — `active_embargo` non-None | **`EmbargoedCase` type** |
| Public / exploit / attacks (P/X/A) | No — `pxa_state` is always present | status flag + precondition |

Plus the pre-case boundary: `IncomingReport` (report data, no case).

So the VulnerabilityCase family is exactly **`IncomingReport` → `Case` →
`EmbargoedCase`**. A `Case` always has ≥1 report and the reporter + receiver
participants (two parties, because Vultron creates the case on receipt and both
sides are present at that moment).

The embargo milestone is monotonic: the EM machine
(`vultron/core/states/em.py`) never returns to `NONE`/`PROPOSED` once `ACTIVE`.

### ParticipantStatus — per-participant RM/vfd (no types)

`rm_state` and `vfd_state` are always-present enum fields. The RM.VALID ratchet
is real (once VALID you cannot return to RECEIVED/INVALID; CLOSED only via
ACCEPTED/DEFERRED) and the vfd path is monotonic (`v→V→F→D`), but neither adds a
field. Per LST-01-001 they earn **no subtype**. They become state-group tuples
and predicates — e.g. `RM_VALIDATED`, `is_rm_validated()` — alongside the
existing `RM_ACTIVE`, `RM_CLOSABLE`, `EM_NEGOTIATING`, and `is_rm_at_least()`
helpers.

### CaseStatus — case-level EM/pxa (no types)

`em_state` and `pxa_state` are always-present enums; no milestone adds a field.
Same outcome as `ParticipantStatus`: predicates + state groups, no subtypes.

## P/X/A: Preconditions, Not Types

The public/exploit/attack dimensions change *which actions are permitted* (you
cannot propose an embargo once any of P/X/A is set; an active embargo must
terminate on publication) but change no field. They are modeled as **precondition
specs + transition guards** (LST-01-002, LST-05), never a `PublicCase` type.
This is deliberately parallel to how RM ratchets are handled — a consistent
principle across all three classes.

## Read Mechanism: model_validate at the Edge

Staged subtypes share `type_="VulnerabilityCase"` (like the `CaseParticipant`
role subclasses share `type_="CaseParticipant"`), so the DataLayer stores them
in one table and rehydrates the **base** type. The staged type is a **view
derived on demand**, not a stored discriminator.

A core function that needs a narrowed type validates at its entry boundary:

```python
# dl.read() returns a generic Case; the edge narrows it.
embargoed = EmbargoedCase.model_validate(case)   # raises if no active embargo
# ... downstream code holds EmbargoedCase; active_embargo is guaranteed.
```

The subtype's own `model_validator` **is** the promotion logic — there is no
separate hand-written promotion function. On invariant violation it raises a
descriptive error at the boundary (fail-fast), never a silent `None` propagated
into core. This is ADR-0032 applied at the read boundary.

## Transition Model: Data Is the Source of Truth

The case *data* is the single source of truth; the stage is **always re-derived,
never stored** (LST-05-002). Advancing a case is an ordinary field mutation
(setting `active_embargo` when EM reaches `ACTIVE`), exactly as today's BT nodes
and use cases already do. No stored "stage" field and no explicit
`transition()` constructors — a second write path would risk divergence from the
existing mutation paths.

*(Recorded at moderate confidence. The alternative — explicit transition
constructors like `case.to_embargoed(embargo)` — is documented in ADR-0033 and
may be reopened if the code-migration audit shows the field-mutation path is
error-prone.)*

## DataLayer Round-Trip Constraint

Round-trip compatibility is a binding design constraint (LST-05-003): a persisted
staged object must rehydrate to the base type and re-validate to its staged type
without loss. Register the base type in `CORE_VOCABULARY` as today; do not add a
persisted stage discriminator.

## Future Direction: Per-Dimension Status Decomposition

A natural next layer — **not** part of ADR-0033 — is decomposing
`CaseStatus`/`ParticipantStatus` into per-machine dimension objects (each state
machine its own small object with its own `transition()`/guard method), e.g.
`ParticipantStatus` → `{report: RmState, fix: VfdState, consent: PecState}`.

Where it helps: it gives the scattered EM/RM transition logic (see
`notes/embargo-lifecycle.md`, #538) one home, models the genuinely independent
dimensions faithfully, and composes with staged types (the `is_rm_validated()`
predicates become methods on the RM dimension). Staged types make illegal
*shapes* unrepresentable; dimension objects make illegal *transitions*
unrepresentable.

Where it gets messier: it is a wire- and persistence-visible schema change
(rehydration, `CORE_VOCABULARY`, AS2 projection, and the append-only
history model all interact), so it deserves its **own ADR** and must not be
folded into the staged-types work. Tracked as a separate Idea issue.
