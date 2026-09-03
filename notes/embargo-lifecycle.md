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
  - notes/call-out-configuration.md
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
   per-participant consent state, over `NO_EMBARGO`, `INVITED`, `SIGNATORY`,
   `LAPSED`, `DECLINED`. `NO_EMBARGO` means *no embargo is in scope*, so
   `ACCEPT`/`DECLINE` are valid directly from it — consent is not always
   mediated by an invitation (ADR-0048, CM-18-003). See
   `notes/participant-embargo-consent.md` for the full transition table and
   the direct-assignment pitfall (CM-18-005).
3. **`VulnerabilityCase.active_embargo`** — the pointer to the currently
   active `VultronEmbargoEvent` object

A correct embargo lifecycle transition must update **all three** consistently.

---

## Current Fragmentation (the problem)

EM state transition logic is currently duplicated across several places:

| Module | Role | Lines | Status |
|---|---|---|---|
| `vultron/core/states/em.py` | EM state machine definition | ~150 | — |
| `vultron/core/states/participant_embargo_consent.py` | PEC machine | ~155 | — |
| `vultron/core/use_cases/triggers/embargo.py` | Trigger-side (5 use-case classes + 10 module-level helpers) | ~902 | needs migration |
| `vultron/core/use_cases/received/embargo.py` | Receive-side (7 use-case classes) | ~482 | needs migration |
| `vultron/core/behaviors/embargo/nodes/` | BT-side autonomous management | — | partially migrated (see below) |

**BT-side migration progress** (EMB-18-001, issue #2480):

- `ClearActiveEmbargoNode` — migrated (PR #2691); routes through
  `EmbargoLifecycle.terminate_active_embargo()`
- `SetEmbargoActiveNode` — migrated (PR #2691, issue #2696); routes through
  `EmbargoLifecycle.activate_embargo()` in STRICT mode; returns FAILURE
  for non-standard EM transitions (EMB-18-002)
- `AdvanceEMStateToActiveNode` — migrated; uses `EmbargoLifecycle.propose_embargo()`
- `WriteEmStateNode` — **retired** (PR #2816, issue #2712); the last BT node
  that directly assigned `EmDimension` to `case.current_status.em`. All five
  `EmbargoLifecycle` service methods now unconditionally own their own EM reads
  and writes. The `caller_owns_em_io` pattern is fully removed.

BT-side direct EM assignment is **complete**. `EmbargoLifecycle` is the single
authoritative owner for EM state writes on the BT side. Trigger-side and
received-side use cases are still pending migration — bugs fixed in the service
will not propagate to them until they are migrated.

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
    def activate_embargo(
        self, *, case_id, embargo_id, actor_id=None, transition_mode=STRICT
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

**Auto-terminate on publication** (CS.P/X/A event): handled by
`PublicDisclosureBranchNode` in `vultron/core/behaviors/status/nodes/lifecycle.py`.
The node is a Selector with two arms depending on the current EM state:

- **EM ACTIVE or REVISE** → delegates to `terminate_embargo_bt` (ET + EM →
  EXITED). This is the cascade path for AC-2 of issue #1454.
- **EM PROPOSED** → delegates to `reject_proposed_embargo_bt` (ER + EM →
  NO_EMBARGO). EMB-16-001: continuing to negotiate a proposed embargo after
  P/X/A is set is not viable; the proposal must be abandoned immediately.
- **EM NO_EMBARGO or EXITED** → skip (nothing to tear down).

Prior to the fix in issue #1892, the skip condition used
`case.active_embargo is None` to detect "no embargo", which silently bypassed
the PROPOSED arm — `active_embargo` is always None when EM is PROPOSED because
the embargo has not yet been activated. The fix checks EM state directly.

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
   BT nodes MUST NOT directly assign `EmDimension` to `case.current_status.em`
   and call `dl.save(case)` as a substitute — route through `EmbargoLifecycle`
   instead (EMB-18-001). Warning-only `is_valid_em_transition()` guards that
   proceed regardless of result MUST NOT be used (EMB-18-002).
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
6. **PROPOSED + P/X/A**: when a CS public/exploit/attacks event fires while EM
   is PROPOSED, use `reject_proposed_embargo_bt` (not `terminate_embargo_bt`).
   `terminate_embargo_bt` requires an active embargo (`HasActiveEmbargoNode`
   guard); it fails when EM is PROPOSED. `reject_proposed_embargo_bt` calls
   `reject_embargo_invite()` which handles PROPOSED → NO_EMBARGO correctly
   (EMB-16-001).

---

## Inbound Embargo-Response Decision (EMB-15)

**Status**: Implemented — PR #1983 / issue #1942. Spec group `EMB-15` in
`specs/em-behavior.yaml`; call-out catalog in
`notes/bt-fuzzer-nodes-embargo.md`.

### Two overture flows the simulator conflated

The pre-PEC simulator collapsed embargo-response into a single
`_ChooseEmProposedResponse` fallback (`vultron/bt/embargo_management/behaviors.py`).
The production protocol separates two distinct inbound overtures:

| | **Flow A — EM proposal** | **Flow B — PEC invitation** |
|---|---|---|
| Inbound message | `ProposeEmbargo` / EP | `InviteToEmbargoOnCase` |
| Question asked | "here are terms" | "become a signatory to this embargo" |
| Accept advances | shared EM (`NONE → PROPOSED → ACTIVE`) | this participant's PEC (`INVITED → SIGNATORY`) |
| Accept mechanism | `accept_embargo_trigger_bt` | `accept_invite_to_embargo_tree` |
| Reject mechanism | `reject_embargo_trigger_bt` (ER; EM → NONE) | `reject_invite_to_embargo_tree` (PEC → DECLINED) |
| Status | **decision layer missing** | mechanics built, **decision layer missing** |

The mechanical BTs for both flows already exist and are purely
transition-recording — they act on whatever arrived. What is missing (and
what #1257 adds) is the **decision layer** that chooses *how to respond*,
layered over both flows as a single seam.

### Design: default-accept with an owner-adjudication seam

Mirrors the two-seam authorization model (ADR-0046) and
`case_proposal_received_tree` (CASE_OWNER gospel bypass → owner-approval
call-out → deterministic default):

```text
Selector (response decision):
  Sequence("AcceptArm"):
    Selector("Authorize"):
      CheckIsCaseOwner            # hard bypass — owner's response is gospel (EMB-15-002)
      CaseOwnerApprovesEmbargoResponse   # call-out; DETERMINISTIC → SUCCESS
    EvaluateEmbargoProposal       # call-out; DETERMINISTIC → SUCCESS (accept, EMB-15-001)
    → delegate to flow-appropriate accept BT
  Sequence("CounterArm"):         # Flow A only (EMB-15-003)
    WillingToCounterEmbargoProposal   # call-out; DETERMINISTIC → FAILURE (off by default)
    → delegate to propose_embargo_trigger_bt (counter = re-propose; no new mechanism)
  RejectArm:                      # (EMB-15-004)
    → delegate to reject_embargo_trigger_bt (Flow A) / reject_invite_to_embargo_tree (Flow B)
```

Hard rule: EMB-01-002 (reject when CS is public/exploit/attacks) overrides the
default-accept policy regardless of adjudication outcome.

### Policy: "shortest embargo wins, then propose extensions"

The recommended CVD default is to **accept** an offered embargo rather than
counter, and negotiate extensions/revisions separately (accept-then-revise).
This is why `EvaluateEmbargoProposal` defaults to accept and
`WillingToCounterEmbargoProposal` defaults to *not* counter. A future
adjudication backend (UI or LLM agent) may poll other participants, apply an
organizational "shortest-embargo-wins" rule, or defer to the case owner — but
that logic lives behind the call-out points, not in the tree.

### Not overtaken; not a monolithic port

Unlike the original Idea framing (one `create_propose_embargo_decision_tree`
mirroring `_ProposeEmbargoBt` + `_ChooseEmProposedResponse` +
`_ChooseEmActiveResponse` as a tick-loop), the outbound "want to propose /
select terms" decision is already the propose trigger use case plus thin
call-out seams in `create_manage_embargo_tree`, and the **active-embargo
review loop** (`CurrentEmbargoAcceptable`) is a continuous-monitoring
Sentinel with no event trigger — tracked separately for monitoring
epic #1147 (companion Idea to #1257), not built here.

## Owner-Close With an Active Embargo: Decline, Do Not Auto-Tear-Down

**Decision (CONCERN-2955, planning group G06 / #2834):** when the Case Owner
tries to close a case that still holds an **active embargo**, the Case Actor
**declines the close** rather than closing. It does not silently tear the embargo
down as part of closure.

The problem: owner-close is a hard, global, terminal write boundary (ADR-0085) —
once the owner leaves, "the front door locks" and the Case Actor accepts no
further external ledger writes. The owner-close path
(`create_close_case_received_tree` → `case_fully_closed`) currently has **no
embargo precondition**, so an owner could close a case out from under an active
embargo, leaving participants under a confidentiality obligation that can never be
discharged through the normal protocol path (no authority remains to lift it).

**Relation to the existing participant-level rules.** The protocol already covers
a *participant* closing/deferring their own report while an embargo is in force,
but only softly and only for the non-terminal case: VP-13-005 (participants
SHOULD NOT close while embargoed), VP-13-007 (a closing participant SHOULD
communicate whether they keep adhering), and VP-13-009 (a participant close
*while other Participants remain engaged* MUST NOT auto-terminate the embargo —
the embargo lives on for the others). Owner-close is the case those rules
explicitly do not reach: it is global and terminal, so there are no "other
Participants" to keep the embargo alive and no authority left to lift it. That is
why the soft participant-level SHOULD_NOT is raised to a hard case-actor MUST
refusal for owner-close specifically (CM-23-011 `refines` VP-13-005).

**The refusal does not terminate the embargo.** Declining the close is *only* a
refusal — it does not tear the embargo down as a side effect. The embargo stays
active until terminated through the normal EM path; only then may the owner
re-issue the close. "Case MUST NOT close while an embargo is live" is the rule —
*not* "case close implies embargo termination."

**Options weighed:**

- **Option A — decline the premature close (chosen).** The Case Actor refuses the
  owner `Leave(VulnerabilityCase)` while an embargo is active and requires an
  explicit terminate-embargo-then-close ordering. Keeps the closure sequence
  simple and atomic, and makes the embargo teardown a deliberate, auditable act by
  the owner rather than an implicit side effect of leaving.
- **Option B — atomic teardown on close (rejected).** Have close implicitly invoke
  the existing `terminate_active_embargo_tree` / `embargo/nodes/teardown.py` as
  part of `case_fully_closed`. Rejected: it buries a significant protocol event
  (embargo termination, which has its own notifications and downstream effects)
  inside the close path, and couples two lifecycle transitions that are cleaner
  kept explicit.

**How the refusal is expressed:** as an **`as:Reject`** response — "received and
understood but declined" (MSM-05-001). The owner's `Leave` is well-formed and
understood; it is *declined* because the embargo is active. It is therefore **not**
a `Create(ProcessingFault)` (that mechanism is for messages received but *not*
understood). Do not use `TentativeReject` — that verb is reserved for declining an
`Offer` (e.g. embargo RSVP / `INVALIDATE_REPORT`), not for refusing a close.

Normative requirement: `specs/case-management.yaml` **CM-23-011**. Implementation
is tracked as a follow-on Task under Epic #2684.

**See**: `docs/adr/0085-case-lifecycle-boundaries.md`;
`specs/case-management.yaml` CM-23-002 / CM-23-011;
`specs/message-semantics-mapping.yaml` MSM-05-001;
`vultron/core/behaviors/case/receive_close_case_tree.py`.
