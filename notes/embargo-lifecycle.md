---
title: Embargo Lifecycle — Architecture and Implementation Notes
status: active
description: >
  Target architecture for EM state management; the inline-EMAdapter
  instantiation anti-pattern in trigger use cases; P/X/A embargo-eligibility
  precondition guards in EmbargoLifecycle; and the fragmentation concern that
  motivates the EmbargoLifecycle service (see #538).
related_specs:
  - specs/case-management.yaml
  - specs/embargo-policy.yaml
related_notes:
  - notes/embargo-default-semantics.md
  - notes/participant-embargo-consent.md
relevant_packages:
  - vultron/core/states/em.py
  - vultron/core/services/embargo_lifecycle.py
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

## Current Architecture (Implemented)

`EmbargoLifecycle` exists at `vultron/core/services/embargo_lifecycle.py` and
owns all EM + PEC transition logic (implemented per
[#538](https://github.com/CERTCC/Vultron/issues/538),
[#746](https://github.com/CERTCC/Vultron/issues/746),
[#747](https://github.com/CERTCC/Vultron/issues/747)).

**Actual public interface**:

```python
class EmbargoLifecycle:
    def __init__(self, persistence: CasePersistence) -> None: ...
    def propose_embargo(
        self, *, case_id, embargo_id, actor_id, transition_mode=STRICT
    ) -> EmbargoLifecycleResult: ...
    def accept_embargo_invite(
        self, *, case_id, embargo_id, actor_id, transition_mode=STRICT
    ) -> EmbargoLifecycleResult: ...
    def reject_embargo_invite(
        self, *, case_id, embargo_id, actor_id, transition_mode=STRICT
    ) -> EmbargoLifecycleResult: ...
    def terminate_active_embargo(
        self, *, case_id, actor_id, transition_mode=STRICT
    ) -> EmbargoLifecycleResult: ...
    def record_participant_consent(
        self, *, case_id, actor_id, pec_trigger, embargo_id=None
    ) -> EmbargoLifecycleResult: ...
```

**`TransitionMode`**: `STRICT` enforces valid transitions and precondition
guards (used by trigger-side BT behaviors).  `OBSERVED` syncs local state
unconditionally to match a remote party's assertion (used by received-side use
cases — bypasses all guards).

**P/X/A embargo-eligibility guards** (added in
[#1454](https://github.com/CERTCC/Vultron/issues/1454)): `EmbargoLifecycle`
enforces EMB-01-002, EMB-02-002, and EMB-04-002 via
`_assert_pxa_embargo_eligible()` in STRICT mode:

- `propose_embargo()` — raises when `pxa_state != CS_pxa.pxa` (any of P/X/A set)
- `accept_embargo_invite()` — raises when owner would drive EM to ACTIVE with
  P/X/A set; non-owner consent recording is not blocked
- `reject_embargo_invite()` — raises when EM is REVISE and P/X/A is set (caller
  MUST use `terminate_active_embargo()` instead)

The received-side path (`received/embargo.py`) does not use `EmbargoLifecycle`
for EM state transitions (those still use inline BT execution), but EMB-01-002
and EMB-02-002 are enforced as explicit pre-flight guards in
`InviteToEmbargoOnCaseReceivedUseCase.execute()` and
`AcceptInviteToEmbargoOnCaseReceivedUseCase.execute()` respectively (implemented
in [#1484](https://github.com/CERTCC/Vultron/issues/1484)). Migrating the
received-side EM transitions to `EmbargoLifecycle` (AC-3 of #1484) is still
pending.

**Auto-terminate on publication** (CS.P event): handled by
`PublicDisclosureBranchNode` in `vultron/core/behaviors/status/nodes/lifecycle.py`,
which delegates to the shared `terminate_embargo_bt` factory. This is the
cascade path for AC-2 of issue #1454.

Trigger use cases are thin orchestrators: resolve actors/cases → call
`EmbargoLifecycle` → build and send the outbound activity.
BT behaviors use `ProposeEmbargoLifecycleNode`, `AcceptEmbargoLifecycleNode`,
`RejectEmbargoLifecycleNode`, and `TerminateEmbargoLifecycleNode` which all
catch `VultronError` and return `Status.FAILURE`.

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

1. **Always use `EmbargoLifecycle`** (`vultron/core/services/embargo_lifecycle.py`).
   Never instantiate `create_em_machine()` + `EMAdapter` inline.
2. **P/X/A precondition**: STRICT mode guards `propose_embargo()` and
   `accept_embargo_invite()` (owner-only) against PXA-set cases.  If your
   caller receives `VultronInvalidStateTransitionError`, the case is no longer
   embargo-eligible — do not attempt to retry; emit ER to the proposer.
3. **REVISE+PXA reject**: `reject_embargo_invite()` raises in STRICT mode when
   EM is REVISE and P/X/A is set — the correct path is
   `terminate_active_embargo()` per EMB-04-002.
4. **PEC cascade is automatic**: `propose_embargo()` cascades `SIGNATORY →
   LAPSED` on `ACTIVE → REVISE`; `terminate_active_embargo()` resets all PEC
   to `NO_EMBARGO`. Callers do not need to do this manually.
5. **OBSERVED mode** (received-side): pass
   `transition_mode=TransitionMode.OBSERVED` to sync local state with a remote
   assertion. All guards and PEC cascades are bypassed in OBSERVED mode.
