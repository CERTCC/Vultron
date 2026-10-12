---
title: Predicate Layer Rule Boundary
status: active
kind: guidance
description: >
  Import constraints for vultron/core/predicates/, when to place a rule there
  rather than inline in a BT node or service, and how to audit for invariants
  enforced on only one path.
related_specs:
  - CSB-15-001
  - CSB-15-002
  - RSH-05-020
related_notes:
  - notes/architecture-hexagonal.md
  - notes/domain-validation.md
relevant_packages:
  - vultron/core/predicates
---

# Predicate Layer (`vultron/core/predicates/`)

The `predicates/` package is the **rule layer** for pure, I/O-free domain
assertions.  It sits *below* every other `core/` sub-package in the import
hierarchy and is the canonical home for enforceable authority and eligibility
rules (#3058).

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

## Audit for One-Sided Invariants (Emit vs. Receive)

An invariant enforced on the emit path but not the receive path is a bug
class: the actor still accepts, hash-chains, and replicates states it would
refuse to emit, and local tests stay green (#2906).

**Audit by grepping, not by reading docstrings.** For each exported
`violation_*` / `is_valid_*` / `is_monotonic_*` predicate in
`vultron/core/states/`, bucket its call sites as **emit** (write nodes,
outbound factories), **receive** (received-side use cases), or
**replica-apply** (`Announce(CaseLedgerEntry)` reconstruction). A predicate
called from only one bucket is a gap unless its docstring or a spec `note:`
states the scoping.

**Fix by composing the rule set, not by adding the missing call.** Compose
the set once (e.g. `composite_state_violations()`), have every path call it, and
add a ratchet test forbidding direct calls to the individual predicates — see
[domain-validation.md §
Compose the rule set, don't just share the predicates](domain-validation.md#compose-the-rule-set-dont-just-share-the-predicates);
the replica-apply rule is RSH-05-020.
