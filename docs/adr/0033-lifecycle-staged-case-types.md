---
status: proposed
date: 2026-07-15
deciders: Allen D. Householder
consulted: Claude Code (design session)
---

# Lifecycle-Staged Domain Types Anchored on Guaranteed-Field Changes

## Context and Problem Statement

`VulnerabilityCase` is the canonical "fat class" named in ADR-0032: one type
represents a case at every lifecycle stage. Core functions that require a case
to have reached a particular stage (e.g. "there is an active embargo") cannot
express that requirement in their type signatures, so they fall back on runtime
guards (`if case.active_embargo is None: ...`,
`if case.current_status.em_state == EM.ACTIVE: ...`).

The Idea (#1362) proposed distinct types per lifecycle stage — illustratively
`IncomingReport`, `TriagedCase`, `ActiveCase` — so a core function accepting a
stage-specific type would reject earlier-stage data at the type level, with no
`if x is None` needed. The Idea explicitly deferred deriving the actual stages
from the protocol until a design was reviewed.

Two protocol facts, verified against the code, shape the answer and make the
naive "one type per RM state" framing unworkable:

1. **RM state is per-participant, not case-universal.** Each `CaseParticipant`
   runs its own RM state machine (`ParticipantStatus.rm_state`). There is no
   such thing as "the case is in RM.VALID" — valid according to *whom*? A case
   type named `ValidCase`/`TriagedCase` would be ill-defined.
2. **Only a few facts are genuinely case-universal.** Case existence,
   structural minimums (≥1 report, reporter + receiver participants), the
   embargo state (`EM`, one per case), and public state (`pxa`) are the only
   monotonic facts that hold case-wide.

## Decision Drivers

- Make illegal *shapes* unrepresentable in core logic (ADR-0032 continuation).
- Do not introduce a type whose fields are identical to its parent's — that is
  ceremony without a type-checker payoff and invites combinatorial proliferation
  (2³ for the independent P/X/A dimensions alone).
- The design must survive DataLayer round-trip: rehydration always yields a
  valid object, so the design must specify how a rehydrated record acquires its
  staged type.
- Reuse the existing precedents: the role-specific `CaseParticipant` subclasses,
  the `RM_ACTIVE` / `EM_NEGOTIATING` state-group tuples, and the
  `is_rm_at_least()` predicate family.

## Considered Options

1. **One type per RM/EM/CS state** — rejected: RM is per-participant, so most
   such types are ill-defined at the case level.
2. **Staged types on every state-bearing class, keyed on any monotonic
   milestone** — rejected: proliferates types that add no fields.
3. **Field-set-anchored staged types** (chosen): a milestone earns a type only
   when it changes the guaranteed (non-None) field set; everything else is
   modeled as predicates + preconditions.

For the *mechanism* of the chosen option, two sub-options were weighed and are
recorded under "Pros and Cons": Pydantic subclasses narrowing fields
(recommended) vs. a discriminated union of sibling types.

## Decision Outcome

Chosen option: **field-set-anchored staged types**.

### Governing principle

> A lifecycle milestone earns a distinct staged **type** only when it changes
> the set of guaranteed (required, non-None) fields. A milestone that only
> changes *which actions are permitted* — without changing which fields are
> present — belongs in the transition model and precondition specs, not the
> type hierarchy.

### What this yields

- **`VulnerabilityCase` staged family (the only staged types):**
  `IncomingReport` → `Case` → `EmbargoedCase`.
  - `IncomingReport`: report data, no case assignment (pre-case).
  - `Case`: a case exists — ADR-0015 creates it at report receipt, so it always
    has ≥1 report, the reporter **and** receiver participants (two parties), and
    a seeded `case_statuses`.
  - `EmbargoedCase`: `em_state ∈ {ACTIVE, REVISE}`, so `active_embargo` is
    **guaranteed non-None**. This is monotonic: EM never returns to
    `NONE`/`PROPOSED` once `ACTIVE` (see `vultron/core/states/em.py`).
- **`ParticipantStatus` and `CaseStatus`: no subtypes.** Their per-participant
  RM/vfd ratchets and case-level EM/pxa ratchets change enum *values*, not the
  field set. They are modeled as **state-group tuples + predicates**
  (`RM_VALIDATED`, `is_rm_validated()`, …) extending the existing
  `RM_ACTIVE`/`EM_NEGOTIATING`/`is_rm_at_least()` helpers.
- **P/X/A option-gating** (e.g. "no embargo may be proposed once the case is
  public, exploit is public, or attacks are observed"; "an active embargo must
  terminate on publication") is modeled as **precondition specs + transition
  guards**, not a `PublicCase` type.

### Read mechanism (promotion at the edge)

The staged subtype's own `model_validator` *is* the promotion logic. A core
function that requires a narrowed type calls
`EmbargoedCase.model_validate(case)` at its entry boundary: on success it holds
the narrow type and the type checker is satisfied downstream; on invariant
violation the validation **raises immediately** — a descriptive fail-fast at the
boundary rather than a silent `None` propagated into core logic. This is
ADR-0032's "validate at the edge, promote to strict core types" applied at the
DataLayer read boundary. There is no separate hand-written promotion function;
the constructor carries the invariant.

### Transition model (write side)

The case *data* is the single source of truth; the staged type is **always
re-derived, never stored**. Advancing a case is an ordinary field mutation
(setting `active_embargo` when EM reaches `ACTIVE`), exactly as today's use
cases and BT nodes already do. No stored "stage" field and no explicit
`transition()` constructors, which would create a second place transitions can
happen and risk divergence from the existing write paths.

*(Recorded at ~70% confidence. The alternative — explicit transition
constructors such as `case.to_embargoed(embargo)` — is documented below and may
be reopened if the code-migration audit shows the field-mutation path is
error-prone in practice.)*

### Consequences

- Good: core function signatures express stage requirements; the type checker
  enforces "this function needs an embargoed case."
- Good: no combinatorial type explosion — P/X/A stay flags; RM/vfd ratchets stay
  predicates.
- Good: consistent single principle across all three state-bearing classes.
- Good: read-boundary narrowing reuses ADR-0032 and Pydantic `model_validate`.
- Neutral: staged subtypes share `type_="VulnerabilityCase"`, so the DataLayer
  stores them in one table and rehydrates the base type; the staged type is a
  *view* derived on demand (see read mechanism). This is deliberate.
- Bad: requires incremental migration of existing core call sites (tracked as a
  follow-up implementation issue).

## Validation

- Full per-stage field inventory written into
  `specs/lifecycle-staged-types.yaml` confirms each staged type adds a
  guaranteed field (else it would not earn a type).
- DataLayer round-trip test: persist an `EmbargoedCase`, `dl.read()` it, and
  `EmbargoedCase.model_validate()` the result successfully; persist a
  pre-embargo `Case` and assert the same validate call raises.
- mypy/pyright clean on the staged-type module.

## Pros and Cons of the Options

### Field-set-anchored staged types (chosen)

- Good, because it introduces types only where they carry a real field
  guarantee.
- Good, because it keeps a single, defensible rule for the whole domain model.
- Neutral, because per-participant/pxa ratchets become predicates rather than
  types.

### Mechanism sub-option A — Pydantic subclasses narrowing fields (recommended)

- Good, because `model_validate` narrowing works for free (the read mechanism).
- Good, because it mirrors the `CaseParticipant` role-subclass proof-of-concept
  and the `CoreObject` `published`/`updated` re-narrowing already in
  `vultron/core/models/base.py`.
- Neutral, because subclasses share the parent `type_`, so the staged type is
  derived on read rather than stored.

### Mechanism sub-option B — discriminated union of sibling types

- Good, because stages are cleanly separated classes.
- Bad, because it does not reuse the existing subclass-narrowing precedent.
- Bad, because it complicates DataLayer type resolution and CORE_VOCABULARY
  registration.

### Transition sub-option — explicit transition constructors (alternative)

- Good, because transitions are centralized and self-documenting.
- Bad, because it adds a second write path alongside the field mutations that
  BT nodes and use cases already perform, risking divergence.

## More Information

Related:

- ADR-0032 — Validate at the Edge, Promote to Strict Core Types (this ADR
  extends it to lifecycle staging and to the read boundary).
- ADR-0015 — Create VulnerabilityCase at Report Receipt (defines the
  `IncomingReport → Case` boundary).
- ADR-0017 — Domain/Wire Object Separation (staged types live on the core
  branch).
- #1362 — the source Idea.
- `notes/lifecycle-staged-types.md` — full design guidance, three-class
  analysis, and the per-dimension-status **Future direction** trailhead.
- `notes/domain-model-separation.md`, `notes/domain-validation.md`.

**Future direction (tracked separately, not this decision):** decomposing
`CaseStatus`/`ParticipantStatus` into per-machine dimension objects (each state
machine its own small object with its own transition method) would make illegal
*transitions* unrepresentable and give the scattered EM/RM logic a home. It is
schema-touching (wire + persistence) and deserves its own ADR.

Generated spec requirements: `lifecycle-staged-types.yaml` LST-01 through LST-05.
