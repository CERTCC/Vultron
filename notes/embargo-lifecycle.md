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
  (EP-09, ADR-0113); and the invariant that a case never names an embargo its
  store cannot read (EMB-18-003).
related_specs:
  - specs/case-management.yaml
  - specs/embargo-policy.yaml
  - specs/em-behavior.yaml
  - specs/message-semantics-mapping.yaml
  - specs/participant-case-replica.yaml
  - specs/received-status-handling.yaml
  - specs/protocol-asks.yaml
related_notes:
  - notes/embargo-default-semantics.md
  - notes/bt-integration.md
  - notes/participant-embargo-consent.md
  - notes/case-communication-model.md
  - notes/case-ledger-authority.md
  - notes/call-out-configuration.md
  - notes/activitystreams-semantics.md
  - notes/protocol-asks.md
relevant_packages:
  - vultron/core/states/em.py
  - vultron/core/services/embargo_lifecycle/
  - vultron/core/services/carried_embargo.py
  - vultron/core/behaviors/embargo/
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
    def record_embargo_rejection(
        self, *, case_id, actor_id, embargo_id
    ) -> EmbargoLifecycleResult: ...
```

`record_embargo_rejection` is the consent half of `reject_embargo_invite` for a
receiver that records a participant's answer without deciding the proposal —
the received `Reject(Invite(EmbargoEvent))` tree calls it through
`RecordParticipantRejectionNode`, so both sides apply one MSM-07-004 rule.

The received-side nodes name their own no-ops and gaps, and the handler keys on
that rather than on the store: `RecordParticipantRejectionNode` prefixes a
repeat of a recorded Reject with `ALREADY_DECLINED_PREFIX` (the handler reports
`SKIPPED`; a `DECLINED` actor's Reject of an *unknown* embargo stays `REFUSED`,
HP-01-003).

### A Case Never Points at an Embargo Its Store Cannot Read (EMB-18-003)

The EP-05-001 comparison reads both the revised embargo B and the embargo A it
replaces, and fails closed on an unreadable one. That is safe only because no
store holds a case whose `active_embargo` names a record it lacks. EMB-18-003
makes that invariant hold by construction rather than repairing it after the
fact. Three kinds of path write `active_embargo`, and each must hold the record
first:

- **Seeding** — a sender carries `active_embargo` inline in every outbound
  case: trigger-built cases through `_case_for_wire`, and the CASE_MANAGER's
  case-proposal `Create(VulnerabilityCase)` through
  `WriteCreateCaseMarkerNode._build_case_object`. A sender whose own store
  cannot read the record has already broken the invariant, so it refuses to
  build the activity (`VultronValidationError`; the marker node fails, logged
  at ERROR) rather than sending a bare id. On receipt, every seeding
  writer calls `store_carried_embargo()`
  (`vultron/core/services/carried_embargo.py`) *before* saving the case:
  `SeedAnnouncedCaseNode`, the create/engage replica stores
  (`_hold_carried_embargo`) and the inbox pre-store of an inbound case. It
  stores an inline `EmbargoEvent` as its own record, then reads the named
  embargo through `read_embargo_event()`; a case naming one the store cannot
  read is refused — the node fails, the handler reports `REFUSED`, the inbox
  pre-store skips the case — and nothing is saved. Extraction reduces an
  inline embargo to its id, so on the received side it is the inbox pre-store
  that holds the carried record before dispatch.
- **Ledger replay** — entries are applied in chain order (SYNC-14-003), and the
  CASE_MANAGER commits A's proposal before any activation that replaces it.
  Each embargo apply node will store the `EmbargoEvent` its entry carries
  before calling `EmbargoLifecycle` (#3915); today the only embargo apply node
  is teardown.
- **The activation writers** — `accept_embargo_invite()` and
  `activate_embargo()`, the only paths that *activate* an embargo (EM state
  plus `active_embargo`). Both compute their EP-05-001 arm through
  `EmbargoLifecycle._activation_arm()` before any write: it reads the
  activated record, and on a revision the replaced one too, so a bare id from
  an inbox (which stores only the first level of nesting: `Accept(Invite(A))`
  keeps the Invite, not A) raises `VultronNotFoundError` or
  `VultronValidationError` in either `TransitionMode` and writes nothing.

So "a replica lacking the replaced embargo" is a broken invariant, not a
replication lag, and no catch-up fetch, replay-on-store trigger, or
`end_time`-in-snapshot mechanism is built for it (CONCERN-4004). Nothing would
re-drive a parked item, so there is no `DEFERRED` arm:
`RecordParticipantAcceptanceNode` reports an unreadable replaced embargo as an
invariant violation logged at ERROR, and the handler reports `REFUSED`
(HP-01-003). An unknown *accepted* embargo stays an ordinary WARNING refusal.

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

The received-side path (`received/embargo.py`) reaches `EmbargoLifecycle`
through nodes: the received Accept runs `accept_embargo_invite(OBSERVED)`
(`RecordParticipantAcceptanceNode`), the received Reject records consent through
`record_embargo_rejection` (`RecordParticipantRejectionNode`) and decides the
proposal through `RemoveFromProposedEmbargoesNode`, and the teardown replay runs
`terminate_active_embargo(OBSERVED)`. The received Invite tree
(`invite_to_embargo_on_case_tree`) has two role-gated arms (#3913, EP-09-001):
in the CASE_MANAGER's store `ProposeEmbargoLifecycleNode(proposer_id=…)` runs
`propose_embargo(STRICT)` — `NONE → PROPOSED`, `ACTIVE → REVISE`, or no move for
a counter-proposal — recording the *proposer's* consent, after a read-only
`EmStateAdmitsProposalNode` guard ahead of the commit has refused an `EXITED`
case; then `RelayEmbargoInviteToEachNode` relays the Invite to every participant
except the proposer, commits each emission and applies PEC `INVITE` where
CM-18-003 allows it. In any other store the tree records the Invite on the
replica (`UpdateParticipantEmbargoPecNode(where_legal=True)`) until #3915 lands
the replay node and gates that write off (RSH-08-004). EMB-01-002 and
EMB-02-002 are enforced as explicit pre-flight guards in
`InviteToEmbargoOnCaseReceivedUseCase.execute()` and
`AcceptInviteToEmbargoOnCaseReceivedUseCase.execute()` respectively (implemented
in [#1484](https://github.com/CERTCC/Vultron/issues/1484)).

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
8. **Reading EM state inside an action node** goes through `ReadEmStateNode`
   (`vultron/core/behaviors/embargo/nodes/em_state.py`), never
   `case.current_status.em` inline (AC-1, #1474; `WriteEmStateNode` was retired
   in #2712 — writes go through the service). The pattern:

   ```python
   result_out: dict[str, object] = {}
   read_node = ReadEmStateNode(case_id=case_id, result_out=result_out)
   read_node.datalayer = self.datalayer
   if read_node.update() != Status.SUCCESS:
       self.feedback_message = read_node.feedback_message
       return Status.FAILURE
   current_em = result_out["em_before"]
   assert isinstance(current_em, EM)
   ```

   Moved here from `vultron/core/behaviors/AGENTS.md` (CONCERN-2559) when that
   file reached its line ceiling.

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
  accepted. No field linking a revision to its embargo is needed.
  `terminate_active_embargo` clears both records through
  `VulnerabilityCase.discard_all_proposed_embargoes` (the whole-record sibling of
  `discard_proposed_embargo`; never by assigning one field), and because the
  teardown replay node (`ClearActiveEmbargoNode`) runs
  `terminate_active_embargo(OBSERVED)`, the rule holds on every replica for free
  (#3914).
- **A Reject names the active embargo or an open proposal — nothing else.**
  `reject_embargo_invite` and `record_embargo_rejection` classify the named
  embargo before the owner's decision prunes it: the active one is consent
  withdrawal, an open proposal is a refusal of those terms, and anything else
  raises `VultronValidationError` (a protocol error, not a consent change;
  ADR-0093). Test seeding that hands the service an embargo the case has never
  seen is therefore a test bug, not a lenient path.

There is **no multi-candidate poll activity** — ADR-0100 retired
`ChoosePreferredEmbargo` (#3469). Offering alternatives means sending several
`Invite`s, each individually dispatchable and individually answerable with
`EA`/`ER`. Automatically re-proposing the remainder as revisions is deliberately
not automated; `propose_embargo_revision_trigger_bt` exists for callers that want
it.

---

## Embargo Negotiation Relays Through the CASE_MANAGER (EP-09, ADR-0113)

The behavioural specs EMB-01 through EMB-06 speak in the voice of the formal
protocol, where every Participant is a peer and every Participant "receives EP"
or "receives EV". In this project's topology a participant addresses its
proposal to the CASE_MANAGER alone (PCR-08-001), so **the Participant receiving
EP or EV is the CASE_MANAGER**, and every other participant learns the resulting
case state from the ledger. Concerns #3892, #3836 and #3863 (revisions), and
Concern #3918 (everything else the rule reaches), all reduced to one question:
how does a proposal become visible to every replica, and what does a participant
do about it? The answer, in order:

1. A participant sends its `Invite(EmbargoEvent)` to the CASE_MANAGER only —
   first proposal or revision alike. The published-default path (EP-04-001)
   emits no proposal, so nothing is relayed for it.
2. The CASE_MANAGER adjudicates it: still embargo-eligible → EM
   `NONE → PROPOSED` or `ACTIVE → REVISE` through `propose_embargo` under the
   role gate (or no transition for a counter-proposal), and the proposal is
   committed; P/X/A set → refused with ER (EMB-01-002, EMB-03-003). The fan-out
   tells replicas the case is under proposal or revision, and that is *all* it
   tells them (EP-09-001).
3. The CASE_MANAGER emits an Invite to **every participant except the
   proposer**, `actor=CASE_MANAGER`, `attributed_to=proposer` (CM-24), each
   carrying `end_time` = its own `published` + the configured RSVP window
   (CM-28-012), and commits each emission (EP-09-002). At that commit it stores
   the deadline on the invitee's record and applies PEC `INVITE` where legal
   (CM-28-013). Proposing terms is consenting to them (ADR-0093), so an Invite
   to the proposer asks an answered question — and the response call-out could
   let a proposer decline its own proposal, a state the protocol has no name for.
4. A participant answers the Invite addressed to it (`Accept`/`Reject` to the
   CASE_MANAGER) through the response decision tree. On receipt it writes **no**
   case, consent or deadline state; consent moves when the CASE_MANAGER commits
   the answer (EP-09-003). The invitee is the sole `to` recipient; anything else
   is refused as a misrouting (EP-09-010). A revision Invite to a `SIGNATORY`
   changes no consent state — `INVITE` is legal only from UNBOUND/LAPSED/DECLINED
   (EP-09-004), so the receive tree must never apply it unconditionally.
5. The owner's answer is consent *and* decision: `Accept` activates
   (`PROPOSED → ACTIVE`, or `REVISE → ACTIVE` with the EP-05-001 cascade),
   `Reject` clears a first proposal or keeps the prior terms. The owner MAY
   decide without waiting (EP-09-005) and SHOULD wait for some answers to gauge
   consensus (EP-09-006); no quorum or vote is defined — that is actor policy,
   a call-out point.
6. Only the CASE_MANAGER evaluates lapse; the lapse entry is role-gated and
   replayed (CM-28-014). Replay nodes reconstruct every step (proposal, each
   Invite, each answer, each lapse, the decision) via `EmbargoLifecycle(OBSERVED)`
   (EP-09-007, RSH-08-004), which is what makes the participant-side embargo
   trees gateable.

**Why invite at all if the owner decides by fiat.** The Invites are not a vote.
They gather the consent records the activation cascade reads: when the owner
activates longer terms, signatories who accepted stay bound and signatories who
did not lapse (EP-05-001). The decision settles the embargo; the answers settle
who is bound by it.

**The ledger never asks.** An `Announce(CaseLedgerEntry)` carrying a proposal or
an Invite sets no parse-and-respond expectation. A participant answers only an
Invite addressed to it. Building a handler for "a non-manager received a peer's
proposal" is building for a misrouting (RSH-08-003: store it, write nothing).

**The commit is the acknowledgement.** The behavioural specs' "emit EK" is
discharged by the CASE_MANAGER's commit and announcement of the received
activity. No EK message exists in production and none is to be built
(EP-09-009, MSM-02-009).

**A trigger writes shared EM state only as the CASE_MANAGER (EP-09-008).** The
five embargo triggers used to write their own local EM state before the manager
answered, then declare it; nothing corrected the write on a refusal. Now the
write sits under the same role gate the received trees use. A non-manager's
trigger emits to the manager, records the activity in the pending-assertion
store (SYNC-11) as the note trigger does, writes nothing and declares nothing;
its replica moves on the announced commit, and the manager's `Reject` closes
the pending entry. Same ordering rule as RSH-08-004: the replay nodes land
before the local write is gated, or a proposer's case never leaves `NONE`.
Participant self-status (RM) keeps its local write — the participant is the
authority on its own progress. ADR-0108 was amended to match.

**The role is never unfilled.** Both creation paths register a `CASE_MANAGER`
holder at birth and delegation hands it on (CM-24-006). No "no manager" arm
belongs in any embargo tree; a resolver that finds nobody fails.

The creation-time revision from shortest-wins follows the same relay
(EP-04-011) — see `notes/embargo-default-semantics.md`.
