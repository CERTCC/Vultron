---
title: Embargo Lifecycle — Architecture and Implementation Notes
status: active
description: >
  Target architecture for EM state management; the inline-EMAdapter
  instantiation anti-pattern in trigger use cases; and the fragmentation
  concern that motivates the EmbargoLifecycle service (see #538).
related_specs:
  - specs/case-management.yaml
  - specs/embargo-policy.yaml
related_notes:
  - notes/embargo-default-semantics.md
  - notes/participant-embargo-consent.md
relevant_packages:
  - vultron/core/states/em.py
  - vultron/core/use_cases/triggers/embargo.py
  - vultron/core/use_cases/received/embargo.py
  - vultron/bt/embargo_management
---

# Embargo Lifecycle — Architecture and Implementation Notes

**Status**: Design decision — target architecture tracked in
[#538](https://github.com/CERTCC/Vultron/issues/538)
**See also**: `notes/embargo-default-semantics.md`,
`notes/participant-embargo-consent.md`

---

## Background

The embargo lifecycle involves three interacting state machines:

1. **EM** (`vultron/core/states/em.py`) — the case-level embargo state:
   `NO_EMBARGO → PROPOSED → ACTIVE ↔ REVISE → EXITED`
2. **PEC** (`vultron/core/states/participant_embargo_consent.py`) — the
   per-participant consent state:
   `NO_EMBARGO → INVITED → SIGNATORY / DECLINED / LAPSED`
3. **`VulnerabilityCase.active_embargo`** — the pointer to the currently
   active `VultronEmbargoEvent` object

A correct embargo lifecycle transition must update **all three** consistently.

---

## Current Fragmentation (the problem)

EM state transition logic is currently duplicated in four places:

| Module | Role | Lines |
|---|---|---|
| `vultron/core/states/em.py` | EM state machine definition | ~150 |
| `vultron/core/states/participant_embargo_consent.py` | PEC machine | ~155 |
| `vultron/core/use_cases/triggers/embargo.py` | Trigger-side (5 use-case classes + 10 module-level helpers) | ~902 |
| `vultron/core/use_cases/received/embargo.py` | Receive-side (7 use-case classes) | ~482 |
| `vultron/bt/embargo_management/` | BT-side autonomous management | ~548 |

There is **no single authoritative place** that owns what it means to
"accept an embargo offer" or "terminate an embargo." The trigger-side and
BT-side implementations are logically parallel but structurally independent —
bugs fixed in one will not propagate to the other.

---

## Anti-Pattern: Inline `EMAdapter` Instantiation in Use Cases

**Do not** instantiate `create_em_machine()` + `EMAdapter` inline inside
trigger or received use-case `execute()` methods. Example of the anti-pattern:

```python
# ❌ WRONG: inline EM machine in execute()
adapter = EMAdapter(em_state)
em_machine = create_em_machine()
em_machine.add_model(adapter, initial=em_state)
try:
    getattr(adapter, "accept")()
except MachineError:
    ...
new_em_state = EM(adapter.state)
```

This pattern appears repeatedly across `triggers/embargo.py` and
`received/embargo.py`. Each repetition is an independent copy of the
transition logic with no shared validation or invariant enforcement.

**Why this is risky:**

- A bug fix or rule change requires updating N copies instead of one.
- The transition validity rules are not documented or enforced by type — a
  typo in the trigger name (e.g., `"accept"` vs `"activate"`) fails silently
  at runtime.
- PEC cascade operations (`_cascade_pec_revise`, `_cascade_pec_reset`) are
  co-located with the EM machine setup but are not guaranteed to run whenever
  the EM state changes.

---

## Target Architecture

[#538](https://github.com/CERTCC/Vultron/issues/538) proposes a single
`vultron/core/services/embargo_lifecycle.py` module with an
`EmbargoLifecycle` service class that owns all EM + PEC transition logic.

**Planned interface sketch** (from #538):

```python
class EmbargoLifecycle:
    def __init__(self, persistence: CasePersistence) -> None: ...
    def propose(self, case_id: str, actor_id: str, ...) -> EM: ...
    def accept(self, case_id: str, actor_id: str, proposal_id: str) -> EM: ...
    def reject(self, case_id: str, actor_id: str, proposal_id: str) -> EM: ...
    def terminate(self, case_id: str, actor_id: str) -> EM: ...
```

Once `EmbargoLifecycle` exists:

- Trigger use cases become thin orchestrators: resolve actors/cases → call
  `EmbargoLifecycle` → build and send the outbound activity.
- Received use cases call the same service in `OBSERVED` mode (state-sync
  without re-enforcing proposal workflow).
- BT behaviors call the same service, eliminating the parallel BT-side
  implementation.

---

## File Size / Complexity Concern

`vultron/core/use_cases/triggers/embargo.py` is tracked in
[#516](https://github.com/CERTCC/Vultron/issues/516) as a high-churn,
high-complexity file. After `EmbargoLifecycle` (#538) lands, a follow-up
audit should confirm:

- File is under 500 lines
- Each testable concern (helper logic, use-case orchestration) is in its own
  module
- No inline `EMAdapter` instantiation remains in use-case `execute()` methods

This follow-up is tracked in a separate issue blocked by #538.

---

## Guidance for Agents

When implementing any code that transitions embargo state:

1. **Check whether `EmbargoLifecycle` exists** (`vultron/core/services/`).
   If it does, use it — do not re-instantiate `create_em_machine()` inline.
2. **If `EmbargoLifecycle` is not yet implemented** (pre-#538), follow the
   existing pattern in `triggers/embargo.py` but leave a `# TODO(#538)`
   comment so the inline instantiation is discoverable for cleanup.
3. **Always cascade PEC** when EM state changes: `ACTIVE → REVISE` must
   trigger `_cascade_pec_revise`; termination must trigger `_cascade_pec_reset`.
   The PEC cascade is not optional.
