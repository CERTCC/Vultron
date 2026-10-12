---
title: Lifecycle-Staged Domain Types
status: active
kind: guidance
description: >
  Rules for lifecycle-staged domain types (ADR-0033): a milestone earns a type
  only when it changes the guaranteed field set; narrow with model_validate at
  the edge (works on dl.read() results); the stage is derived, never stored; the
  write path stays field mutation.
related_specs:
  - specs/lifecycle-staged-types.yaml
  - specs/architecture.yaml
related_notes:
  - notes/domain-validation.md
  - notes/case-state-model.md
relevant_packages:
  - vultron/core/models
  - vultron/core/states
---

# Lifecycle-Staged Domain Types

Normative requirements: `specs/lifecycle-staged-types.yaml` (LST-01 to LST-05);
decision and rejected alternatives: ADR-0033; types:
`vultron/core/models/staged_case.py`.

## A Milestone Earns a Type Only If It Changes the Guaranteed Fields

> A lifecycle milestone earns a distinct staged **type** only when it changes the
> set of guaranteed (required, non-None) fields. A milestone that only changes
> *which actions are permitted* belongs in the transition model and precondition
> specs, not the type hierarchy (LST-01-001).

Without this rule types proliferate (P/X/A alone would imply 2³ combinations).
Applied to the three state-bearing classes:

| Class | Milestone | Result |
|---|---|---|
| `VulnerabilityCase` | case exists (participants, reports, seeded status) | `Case` type |
| `VulnerabilityCase` | embargo active (`active_embargo` non-None) | `EmbargoedCase` type |
| `VulnerabilityCase` | public / exploit / attacks | precondition + guard, never `PublicCase` (LST-01-002) |
| `ParticipantStatus` | RM ratchets, vfd progress | state groups and predicates (`RM_VALIDATED`, `is_rm_at_least()`) |
| `CaseStatus` | EM / pxa changes | state groups and predicates |

Plus the pre-case boundary `IncomingReport`. RM state is per-participant, so
"the case is valid" is undefined and earns no case type.

## Narrow With `model_validate` at the Edge

Staged subtypes share `type_="VulnerabilityCase"`, so the DataLayer stores one
table and rehydrates the **base** type. A function needing a narrowed type
validates at its entry boundary:

```python
embargoed = EmbargoedCase.model_validate(case)   # raises if no active embargo
```

The subtype's `model_validator` **is** the promotion logic; write no separate
promotion function. It raises at the boundary, never returns `None` into core
(ADR-0032). This works on a real `dl.read()` result, not only on a
core-constructed object (`test_staged_case.py`,
`TestDataLayerRoundTrip::test_promotion_works_on_a_real_datalayer_read`).
An upstream BT guard such as `HasActiveEmbargoNode` is an alternative placement
for the same precondition, not evidence that promotion fails.

## The Stage Is Derived, Never Stored

Case data is the single source of truth; the stage is re-derived on demand
(LST-05-002). Do not add a persisted stage discriminator: a staged object must
rehydrate to the base type and re-validate to its staged type without loss
(LST-05-003). Register only the base type in `CORE_VOCABULARY`.

## The Write Path Stays the Existing One

Advancing a case goes through the write path that already owns the data: an
embargo becomes active through an `EmbargoLifecycle` register step, and
`active_embargo` is a read-only view of the register's `ACTIVE` entry
(ADR-0122). Do not add transition constructors such as
`case.to_embargoed(embargo)`: a second write path would diverge from the
existing one (ADR-0033, CONCERN-1912). Reopen only on **two or more distinct
classes of write error** observed at promotion sites (for example, promoting to
`EmbargoedCase` from a case whose register has no `ACTIVE` entry).
