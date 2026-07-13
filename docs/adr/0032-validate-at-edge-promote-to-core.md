---
status: accepted
date: 2026-07-13
deciders: Allen D. Householder
---

# Validate at the Edge, Promote to Strict Core Types

## Context and Problem Statement

Core domain helpers throughout `vultron/core/` are peppered with
`if x is None: return None` chains. These silent failures propagate far from
their source — the error surfaces at the point of *use* rather than the point
of *origin*, making debugging difficult and creating a class of bug where
program state is quietly corrupted or silently skipped.

The root cause is structural: loose wire-layer types (where `Optional` fields
are correct — AS2 permits many fields to be absent) leak directly into core
logic without being promoted to tighter representations. Core functions then
defensively guard every field they actually require.

A secondary symptom is collection-typed fields and parameters that default to
`None` instead of an empty collection, forcing every call-site to write
`x or []` / `x or {}` boilerplate before iteration.

The DataLayer already established the right precedent: `dl.read()` raises
`VultronNotFoundError` rather than returning `None`. This ADR generalises that
precedent to all core domain helpers and domain model fields.

## Decision Drivers

- Silent `None` propagation causes failures far from the error source.
- Core functions should express their contracts in their type signatures.
- The type system should make illegal states unrepresentable within core logic.
- Idiomatic Python prefers `raise` over sentinel return values (EAFP culture).
- `dl.read()` raising `VultronNotFoundError` is an existing, working precedent
  to generalise from.

## Considered Options

1. **Return `None` and guard at every call-site** — current pattern.
2. **`Result`/`Option` monadic types** (e.g. the `returns` library).
3. **One rich domain class with Optional fields and `None` guards in core**.
4. **Validate at the edge, promote to strict core types** (chosen).

## Decision Outcome

Chosen option: **Validate at the edge, promote to strict core types**, because
it is idiomatic Python, fail-fast, provides a stack trace pointing to the
origin of the error, and allows the type checker to verify guarantees.

The pattern in three steps:

1. **Edge objects may be loose.** Wire-layer and adapter Pydantic models may
   have `Optional` fields where the protocol or external source permits absence.
2. **Promote at the boundary.** At the boundary (extractor, rehydration layer,
   use-case entry point), required fields are validated. If absent, a
   descriptive exception is raised immediately — not propagated as `None`.
3. **Core receives strict types.** What crosses into core logic is a type that
   makes the required fields non-optional. Core functions declare these tighter
   types in their signatures; the type system enforces the contract.

The Vultron analogy for the blog post's drone pattern:
`VultronActivity` (wire, loose) → validated at extractor/rehydration →
`FooReceivedEvent` or use-case request type (core, tight).
The role-specific `CaseParticipant` subclasses (`VendorParticipant`, etc.)
are a partial implementation of this pattern already in the codebase.

### Corollary — Collection defaults

Collection-typed fields on domain objects default to the appropriate empty
collection (`[]`, `{}`, `set()`), not `None`. Use
`field(default_factory=list)` etc. in Pydantic models and dataclasses.
`None` is reserved for fields where absence is semantically distinct from
empty (e.g. AS2 fields where `None` omits the key from the wire payload).

### Corollary — BT node helpers raise; `update()` catches

BT node helper methods must either complete successfully or raise a domain
exception (e.g. `BtNodePreconditionError`). They must not return `None` as a
failure signal. The `update()` method is the single `try/except` handler that
converts the exception to `Status.FAILURE` and sets `self.feedback_message`.

```python
# GOOD — helper raises; update() catches
def _read_case_obj(self, case_id: str) -> VulnerabilityCase:
    try:
        obj = self.blackboard[case_id]
    except KeyError:
        raise BtNodePreconditionError(f"case {case_id!r} not in blackboard")
    if not is_case_model(obj):
        raise BtNodePreconditionError(
            f"blackboard entry {case_id!r} is not a VulnerabilityCase"
        )
    return obj

def update(self, ...) -> Status:
    try:
        case_obj = self._read_case_obj(case_id)
        ...
    except BtNodePreconditionError as e:
        self.feedback_message = str(e)
        return Status.FAILURE
```

This eliminates the class of bug where a helper returns `None` silently with
no `self.feedback_message` set.

### Consequences

- Good: stack traces point to the origin of the error, not the point of use.
- Good: type checker can verify that core functions receive guaranteed types.
- Good: eliminates `if x is None: return None` boilerplate in core helpers.
- Good: eliminates `x or []` / `x or {}` boilerplate at call-sites.
- Good: aligns BT node helpers with the `dl.read()` precedent.
- Bad: requires migration of existing code; tracked in #1359 and #1360.
- Bad: BT node helpers need a custom exception class (`BtNodePreconditionError`
  or similar) before they can adopt the raise pattern.

## Validation

- `test/architecture/test_core_no_adapter_imports.py` (existing ratchet) —
  no new violations.
- New code in `vultron/core/` reviewed to confirm helpers raise rather than
  returning `None` on failure.
- mypy / pyright clean on amended files.

## Pros and Cons of the Options

### Option 1 — Return `None`, guard at every call-site

- Bad, because silent propagation: error origin and use-point diverge.
- Bad, because every caller must guard or risk a silent no-op.
- Bad, because "forgot to guard" produces no error until the `None` is used.

### Option 2 — `Result`/`Option` monadic types

- Good, because type-safe and explicit.
- Bad, because it fights Python's EAFP culture.
- Bad, because it adds a library dependency (`returns` or equivalent).
- Bad, because it is an unfamiliar idiom for most Python contributors.

### Option 3 — One rich domain class, Optional fields, None guards in core

- Bad, because it is the "fat class" antipattern.
- Bad, because it makes illegal states representable within core logic.
- Bad, because validation burden spreads to every consumer of the class.
- `VulnerabilityCase` is the canonical example in this codebase: one class
  representing a case at every lifecycle stage, forcing Optional fields
  everywhere. See issue #1361 for the design exploration of lifecycle-staged
  replacements.

### Option 4 — Validate at edge, promote to strict types (chosen)

- Good, because idiomatic Python (EAFP).
- Good, because fail-fast with useful stack traces.
- Good, because type signatures express contracts.
- Good, because `dl.read()` already proves the pattern works in this codebase.
- Neutral, because migration of existing code is required incrementally.

## More Information

Related:

- #1359 — Implementation: collection defaults (`None` → empty collection)
- #1360 — Implementation: core helpers raise instead of returning `None`
- #1361 — Idea: lifecycle-staged `VulnerabilityCase` types
- `notes/architecture-hexagonal.md` — hexagonal rules (updated by this ADR)
- `notes/bt-integration.md` — BT node helper rules (updated by this ADR)
- `notes/datalayer-design.md` — `dl.read()` raising `VultronNotFoundError`
  (the precedent this ADR generalises)
- `notes/domain-model-separation.md` — wire/domain/persistence separation
  and the `FooActivity` → `FooEvent` promotion pattern

Generated spec requirements: architecture.yaml ARCH-10-001
