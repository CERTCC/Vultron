---
title: Embargo Lifecycle — Architecture and Implementation Notes
status: active
description: >
  Target architecture for EM state management; the inline-EMAdapter
  instantiation anti-pattern in trigger use cases; P/X/A embargo-eligibility
  precondition guards in EmbargoLifecycle; the earliest-expiration resolution
  order for multiple open proposals (EP-08); and the fragmentation concern that
  motivates the EmbargoLifecycle service (see #538).
related_specs:
  - specs/case-management.yaml
  - specs/embargo-policy.yaml
related_notes:
  - notes/embargo-default-semantics.md
  - notes/participant-embargo-consent.md
  - notes/call-out-configuration.md
  - notes/activitystreams-semantics.md
  - notes/protocol-asks.md
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
   `NONE → PROPOSED → ACTIVE ↔ REVISE → EXITED`
2. **PEC** (`vultron/core/states/participant_embargo_consent.py`) — the
   per-participant consent state, over `UNBOUND`, `INVITED`, `SIGNATORY`,
   `LAPSED`, `DECLINED`. `UNBOUND` means *the participant is not bound by any
   embargo terms*, so `ACCEPT`/`DECLINE` are valid directly from it — consent
   is not always mediated by an invitation (ADR-0048, ADR-0091, CM-18-003). See
   `notes/participant-embargo-consent.md` for the full transition table and
   the direct-assignment pitfall (CM-18-005).
3. **`VulnerabilityCase.active_embargo`** — the pointer to the currently
   active `EmbargoEvent` object

A correct embargo lifecycle transition must update **all three** consistently.

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
  NONE). EMB-16-001: continuing to negotiate a proposed embargo after
  P/X/A is set is not viable; the proposal must be abandoned immediately.
- **EM NONE or EXITED** → skip (nothing to tear down).

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
   to `UNBOUND`. Callers do not need to do this manually.
5. **OBSERVED mode** (received-side): pass
   `transition_mode=TransitionMode.OBSERVED` to sync local state with a remote
   assertion. All guards and PEC cascades are bypassed in OBSERVED mode.
6. **PROPOSED + P/X/A**: when a CS public/exploit/attacks event fires while EM
   is PROPOSED, use `reject_proposed_embargo_bt` (not `terminate_embargo_bt`).
   `terminate_embargo_bt` requires an active embargo (`HasActiveEmbargoNode`
   guard); it fails when EM is PROPOSED. `reject_proposed_embargo_bt` calls
   `reject_embargo_invite()` which handles PROPOSED → NONE correctly
   (EMB-16-001).
7. **Several proposals can be open at once, and order is by expiration, not
   arrival** (EP-08, ADR-0100). See the section below before touching any
   proposal-selection code.

---

## Open Proposals Resolve Earliest-Expiration First (EP-08)

`EM.PROPOSED` means "one or more embargo proposals under negotiation", and more
than one is ordinary rather than exceptional: EMB-15-003 routes a counter-proposal
through the *existing* propose path, which emits a fresh EP while the state stays
PROPOSED. `VulnerabilityCase.pending_embargo_proposal_index` (embargo id →
proposal id) therefore routinely holds several entries.

`docs/topics/process_models/em/defaults.md` is normative and says a Participant
SHOULD accept the **earliest-expiring** open proposal and handle the rest as
revisions — the *Shortest Embargo Proposed Wins* heuristic. EP-08 states it in
`specs/` so it is testable. **This is not what the code did**, which is the whole
reason EP-08 exists:

- `find_embargo_proposal_id` returned the *first recorded* proposal, so after a
  counter-proposal a default `accept` took the **superseded** terms. Fixed by
  #3470.
- **Neither record of open proposals is fully pruned.** Nothing at all removes a
  decided entry from `pending_embargo_proposal_index` — one writer, no remover.
  The neighbouring `proposed_embargoes` list is pruned *only on teardown*, by
  `RemoveFromProposedEmbargoesNode`, which is wired into
  `remove_embargo_from_case_tree` and nowhere else; `reject_proposed_embargo_bt`
  omits it, so a **rejected** proposal survives in both records.
  `reject_proposed.py` only reads the list. An unpruned record is not a weaker
  guarantee than a pruned one; it is a different and wrong answer, because a
  decided proposal stays selectable. Both records are #3470's job.

Two rules follow for any new proposal-selection code:

- **Never select by insertion or arrival order.** Resolve candidates' embargo
  `end_time` and take the earliest. `#3392` needs the same comparison for
  EP-04-003 shortest-wins at case creation — use one shared comparator, not two.
- **Prune on decision, in both records and on every decision path.** Teardown is
  the only path that prunes anything today; accept and reject prune nothing. Two
  records of overlapping state, each pruned on a different subset of the decision
  paths, is exactly the drift EP-08-003 closes.

There is **no multi-candidate poll activity** — ADR-0100 retired
`ChoosePreferredEmbargo` (#3469). Offering alternatives means sending several
`Invite`s, each individually dispatchable and individually answerable with
`EA`/`ER`. Automatically re-proposing the remainder as revisions is deliberately
not automated; `propose_embargo_revision_trigger_bt` exists for callers that want
it.

---
