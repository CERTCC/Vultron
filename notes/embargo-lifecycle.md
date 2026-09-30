---
title: Embargo Lifecycle — Architecture and Implementation Notes
status: active
description: >
  Target architecture for EM state management; the inline-EMAdapter
  instantiation anti-pattern in trigger use cases; P/X/A embargo-eligibility
  precondition guards in EmbargoLifecycle; the earliest-expiration resolution
  order for multiple open proposals (EP-08); and the fragmentation concern that
  motivates the EmbargoLifecycle service (see #538); and the revision relay
  through the CASE_MANAGER, under which the ledger carries state but never asks
  (EP-09, ADR-0113).
related_specs:
  - specs/case-management.yaml
  - specs/embargo-policy.yaml
  - specs/em-behavior.yaml
  - specs/message-semantics-mapping.yaml
  - specs/participant-case-replica.yaml
  - specs/received-status-handling.yaml
related_notes:
  - notes/embargo-default-semantics.md
  - notes/participant-embargo-consent.md
  - notes/case-communication-model.md
  - notes/case-ledger-authority.md
  - notes/call-out-configuration.md
  - notes/activitystreams-semantics.md
  - notes/protocol-asks.md
relevant_packages:
  - vultron/core/states/em.py
  - vultron/core/services/embargo_lifecycle/
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

`EmbargoLifecycle` exists at `vultron/core/services/embargo_lifecycle/` (a package
since #3760, one module per responsibility; see its `__init__` docstring) and
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

1. **Always use `EmbargoLifecycle`** (`vultron/core/services/embargo_lifecycle/`).
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
4. **PEC cascade is automatic**: `propose_embargo()` changes no consent — a
   proposal binds nobody (ADR-0093, EP-05-002) — and records the proposer's
   consent to the proposed id. The owner path of `accept_embargo_invite()`
   re-evaluates consent when it replaces the active embargo: signatories who
   have not accepted *longer* terms lapse, and a *shorter* replacement carries
   everyone over (MSM-07-005). `terminate_active_embargo()` resets all PEC to
   `UNBOUND`. Callers do not need to do this manually.
5. **OBSERVED mode** (received-side): pass
   `transition_mode=TransitionMode.OBSERVED` to sync local state with a remote
   assertion. EM transition guards are bypassed in OBSERVED mode; the PEC
   cascades still run, so a replica's consent records stay in step with the
   CASE_MANAGER's.
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
- **Prune on decision, in both records and on every decision path.** Before #3470
  teardown was the only path that pruned anything, and it pruned only
  `proposed_embargoes`; accept and reject pruned nothing. Two records of overlapping
  state, each pruned on a different subset of the decision paths, is exactly the
  drift EP-08-003 closes: `VulnerabilityCase.discard_proposed_embargo` now forgets
  a decided proposal in both records, and every `EmbargoLifecycle` decision (owner
  accept, owner reject, activation, termination) and `RemoveFromProposedEmbargoesNode`
  call it. A participant's accept or reject is consent, not a decision, and prunes
  nothing. Replicas prune too: the received Accept goes through
  `accept_embargo_invite`, and the received `Reject(Invite)` tree appends
  `RemoveFromProposedEmbargoesNode(decided_by=<rejecting actor>)`, which prunes only
  when that actor is the case owner — without it the owner's Reject left the decided
  proposal in every participant's records, where a later default selection could still
  pick it. Termination decides *every* open proposal, not only the terminated
  embargo's own entry (EP-08-004, ADR-0113): a case has one active embargo
  (VP-04-002), so every proposal open while EM is `ACTIVE` or `REVISE` is a
  revision of it, and a revision of an embargo that no longer exists cannot be
  accepted. No field linking a revision to its embargo is needed. Because the
  teardown replay node runs `terminate_active_embargo(OBSERVED)`, the rule holds
  on every replica for free.

There is **no multi-candidate poll activity** — ADR-0100 retired
`ChoosePreferredEmbargo` (#3469). Offering alternatives means sending several
`Invite`s, each individually dispatchable and individually answerable with
`EA`/`ER`. Automatically re-proposing the remainder as revisions is deliberately
not automated; `propose_embargo_revision_trigger_bt` exists for callers that want
it.

---

---

## Revision Negotiation Relays Through the CASE_MANAGER (EP-09, ADR-0113)

The behavioural specs EMB-03 through EMB-05 speak in the voice of the formal
protocol, where every Participant is a peer and every Participant "receives EV".
In this project's topology a participant addresses its proposal to the
CASE_MANAGER alone (PCR-08-001), so **the Participant receiving EV is the
CASE_MANAGER**, and every other participant learns the resulting case state
from the ledger. Concerns #3892, #3836 and #3863 all reduced to one question:
how does a revision proposal become visible to every replica, and what does a
participant do about it? The answer, in order:

1. A participant sends its `Invite(EmbargoEvent)` to the CASE_MANAGER only.
2. The CASE_MANAGER adjudicates it: still embargo-eligible → EM
   `ACTIVE → REVISE` through `propose_embargo` under the role gate (or no
   transition for a counter-revision), and the proposal is committed; P/X/A set →
   refused with ER (EMB-03-003). The fan-out tells replicas the case is under
   revision, and that is *all* it tells them (EP-09-001).
3. The CASE_MANAGER emits a revision Invite to **every participant except the
   proposer**, `actor=CASE_MANAGER`, `attributed_to=proposer` (CM-24), and
   commits each emission (EP-09-002). Proposing terms is consenting to them
   (ADR-0093), so an Invite to the proposer asks an answered question — and the
   response call-out could let a proposer decline its own proposal, a state the
   protocol has no name for.
4. A participant answers the Invite addressed to it (`Accept`/`Reject` to the
   CASE_MANAGER) through the response decision tree. On receipt it writes **no**
   case or consent state; consent moves when the CASE_MANAGER commits the answer
   (EP-09-003). A revision Invite to a `SIGNATORY` changes no consent state —
   `INVITE` is legal only from UNBOUND/LAPSED/DECLINED (EP-09-004), so the receive
   tree must never apply it unconditionally.
5. The owner's answer is consent *and* decision: `Accept` activates the revision
   (with the EP-05-001 cascade), `Reject` keeps the prior terms. The owner MAY
   decide without waiting (EP-09-005) and SHOULD wait for some answers to gauge
   consensus (EP-09-006); no quorum or vote is defined — that is actor policy,
   a call-out point.
6. Replay nodes reconstruct every step (proposal, each Invite, each answer, the
   decision) via `EmbargoLifecycle(OBSERVED)` (EP-09-007, RSH-08-004), which is
   what makes the participant-side embargo trees gateable.

**Why invite at all if the owner decides by fiat.** The Invites are not a vote.
They gather the consent records the activation cascade reads: when the owner
activates longer terms, signatories who accepted stay bound and signatories who
did not lapse (EP-05-001). The decision settles the embargo; the answers settle
who is bound by it.

**The ledger never asks.** An `Announce(CaseLedgerEntry)` carrying a proposal or
an Invite sets no parse-and-respond expectation. A participant answers only an
Invite addressed to it. Building a handler for "a non-manager received a peer's
proposal" is building for a misrouting (RSH-08-003: store it, write nothing).

**Emit-side optimism, left alone.** A proposer's trigger still moves its own
local EM to `REVISE` before the CASE_MANAGER answers. ADR-0108 left the emit
side unchanged; do not read that local write as the mechanism by which the case
moved.

The creation-time revision from shortest-wins follows the same relay
(EP-04-011) — see `notes/embargo-default-semantics.md`.
