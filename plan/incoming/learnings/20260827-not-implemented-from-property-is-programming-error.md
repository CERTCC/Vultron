---
title: "NotImplementedError from a port property is a programming error, not a data condition"
type: learning
timestamp: "2026-08-27T00:00:00Z"
source: ISSUE-2668
signal: design-question
---

When a `CasePersistence` (or similar port) stub raises `NotImplementedError`
from its `actor_id` property, callers like `resolve_receiving_actor_id` see the
exception propagate past the `getattr(dl, "actor_id", None)` default.

**Decision**: do NOT wrap the `getattr` in `try/except NotImplementedError`.

**Why**: A property that raises `NotImplementedError` is a broken adapter — a
programming error, not an "actor not available" data condition.  Catching it and
converting it to `VultronValidationError("cannot resolve receiving actor")` would
produce a misleading diagnosis: callers would see a data-problem error when the
real issue is an unimplemented adapter.  The unambiguous signal of `NotImplementedError`
propagating is MORE useful than the masked `VultronValidationError`.

**Contrast with the `ValueError` pattern** documented in `notes/domain-validation.md`:
`ValueError` can be raised from a *correctly-implemented* property when data
preconditions are not met (e.g., `VulnerabilityCase.current_status` with no
materialised entries) — so catching it is correct there.  `NotImplementedError` is
categorically different: it signals an **absent implementation**, not a valid
runtime data state.

**How to apply**: when a port method/property MAY raise `NotImplementedError`,
update the port contract docstring to say "MUST NOT raise `NotImplementedError`"
and add a test that documents propagation as the programming-error signal.  Do NOT
add a try/except guard that masks it.
