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

## Auditing for One-Sided Invariants (Emit vs. Receive)

"The same protocol invariant is enforced on the emit path but not the receive
path" is a discoverable **bug class**, and it is strictly worse than a check
missing on *both* sides. When only the emit path enforces it, the local actor's
own behavior looks correct while it will still accept, hash-chain, and replicate
states it would refuse to emit — so the gap hides behind a green local test
suite and surfaces only when a peer sends the state the emitter would never
produce.

**Audit technique (do it mechanically).** For each invariant module in
`vultron/core/states/`, take every exported `violation_*` / `is_valid_*` /
`is_monotonic_*` predicate and list its call sites, bucketed by path:

- **emit** — write nodes / factories building an outbound activity,
- **receive** — received-side use cases applying an inbound activity,
- **replica-apply** — `Announce(CaseLedgerEntry)` reconstruction on other actors.

A predicate with callers on only one bucket is either a deliberate scoping
decision — which **MUST** be stated in the predicate's docstring or a spec
`note:` — or a gap. Do the bucketing by grepping call sites, not by reading
prose: a manual pass on ISSUE-2906 trusted a docstring and missed a predicate
that had no live caller at all.

**Structural fix (not just a patch).** Don't fix the gap by adding the missing
call; compose the rule *set* once (e.g. `cross_machine_violations()`) and have
every path invoke that set, guarded by a ratchet test that forbids direct calls
to the individual predicates. Composing the set — not merely sharing the
predicates — is what makes divergence impossible rather than repeatedly
re-fixed. See [domain-validation.md](domain-validation.md) §
[Compose the rule set, don't just share the predicates](domain-validation.md#compose-the-rule-set-dont-just-share-the-predicates)
for that pattern; the concrete replica-apply rule is recorded as RSH-05-020.

*Source: ISSUE-2906.*
