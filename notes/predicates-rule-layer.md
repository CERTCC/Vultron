---
title: Predicate Layer Rule Boundary
status: active
description: >
  Import constraints, module inventory, and guidance for when to place a rule
  in vultron/core/predicates/ rather than inline in a BT node or service.
related_specs:
  - CSB-15-001
  - CSB-15-002
  - CM-25-005
  - EMB-01-002
  - EMB-02-002
related_notes:
  - notes/architecture-hexagonal.md
relevant_packages:
  - vultron/core/predicates
---

# Predicate Layer (`vultron/core/predicates/`)

The `predicates/` package is the **rule layer** for pure, I/O-free domain
assertions.  It sits *below* every other `core/` sub-package in the import
hierarchy and is the canonical home for enforceable authority and eligibility
rules (ISSUE-3058).

## Boundary rules

| Direction | Rule |
|---|---|
| `predicates/` **MAY** import from | `vultron.core.states`, `vultron.enums` |
| `predicates/` **MUST NOT** import from | `vultron.core.behaviors`, `vultron.core.use_cases`, `vultron.core.services`, `vultron.core.ports` |
| `behaviors/`, `use_cases/`, `services/` **MAY** import from | `predicates/` |
| `states/` **MUST NOT** import from | `predicates/` (would create a cycle) |

## When to put a rule in `predicates/`

- Any inline `CVDRole.X in roles` check in a BT node or service method → move
  to a named function in `predicates/roles.py`.
- Any inline eligibility check (embargo window, state invariant) → move to
  the appropriate `predicates/` module.
- Any function that is *only* pure and testable with in-memory values belongs
  here; functions that need DataLayer access stay in `behaviors/` or
  `services/`.

## Modules

- `participants.py` — predicates over `CaseParticipant` lists (e.g., RM
  convergence)
- `roles.py` — role-membership and role-gated state invariant predicates
  (CSB-15-001, CSB-15-002, CM-25-005, ADR-0057, ADR-0084)
- `embargo.py` — embargo-eligibility predicates (EMB-01-002, EMB-02-002)
