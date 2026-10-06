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
  (EP-09, ADR-0113), including who records an answer and how RSH-04-002
  reads on the relay trees; the invariant that a case never names an
  embargo its store cannot read (EMB-18-003); and the trigger write gate under
  which only the CASE_MANAGER writes and commits shared EM state while any
  other participant asks (EP-09-008, SYNC-11-002, EMB-19-001), including
  the P/X/A abandonment of every open proposal (EMB-16-001), which a
  non-manager neither writes nor asks for (EMB-16-002) while still answering
  with ER any proposal it receives at P/X/A (EMB-01-002), and the replica that
  leaves a CASE_MANAGER-declared teardown to its entry (RSH-03-004); a
  non-manager replica's cascade teardown ask is a pending assertion, so a
  repeat P/X/A signal queues no second ask (SYNC-11-002); and who may send
  each received embargo message (ADR-0115, HP-01-006).
related_specs:
  - specs/case-management.yaml
  - specs/embargo-policy.yaml
  - specs/em-behavior.yaml
  - specs/message-semantics-mapping.yaml
  - specs/participant-case-replica.yaml
  - specs/received-status-handling.yaml
  - specs/protocol-asks.yaml
  - specs/sync-ledger-replication.yaml
  - specs/behavior-tree-integration.yaml
  - specs/handler-protocol.yaml
  - specs/case-ledger-processing.yaml
related_notes:
  - notes/embargo-default-semantics.md
  - notes/bt-integration.md
  - notes/participant-embargo-consent.md
  - notes/case-communication-model.md
  - notes/case-ledger-authority.md
  - notes/call-out-configuration.md
  - notes/activitystreams-semantics.md
  - notes/received-status-authorization.md
  - notes/protocol-asks.md
relevant_packages:
  - vultron/core/states/em.py
  - vultron/core/services/embargo_lifecycle/
  - vultron/core/services/carried_embargo.py
  - vultron/core/behaviors/embargo/
  - vultron/core/behaviors/embargo/nodes/relay_effect.py
  - vultron/core/behaviors/embargo/nodes/manager_commit.py
  - vultron/core/models/pending_assertion.py
  - vultron/core/use_cases/triggers/embargo.py
  - vultron/core/use_cases/received/embargo/
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
   per-participant, per-embargo consent rows (`CaseParticipant.embargo_consents`),
   each `INVITED`, `ACCEPTED`, `DECLINED` or `EXPIRED` (ADR-0122). A participant
   with no row for an embargo is not bound by it, so `ACCEPT`/`DECLINE` are
   valid directly from no row — consent is not always mediated by an invitation
   (ADR-0048, CM-18-003). "Signatory" (the active embargo's row is `ACCEPTED`)
   and "lapsed" are read from the rows, never stored. See
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
    def initialize_creation_embargo(
        self, *, case_id, embargo, actor_id=None, revision=None
    ) -> EmbargoLifecycleResult: ...  # NONE → ACTIVE, one write; stores embargo
    def record_participant_consent(
        self, *, case_id, actor_id, pec_trigger, embargo_id=None
    ) -> EmbargoLifecycleResult: ...
    def record_embargo_rejection(
        self, *, case_id, actor_id, embargo_id
    ) -> EmbargoLifecycleResult: ...
    def record_embargo_invite(
        self, *, case_id, invitee_id, rsvp_deadline=None
    ) -> EmbargoLifecycleResult: ...  # PEC INVITE, EM unchanged
    def detect_and_apply_lapse(
        self, *, case_id, actor_id, now
    ) -> EmbargoLifecycleResult: ...  # lazy RSVP-deadline DECLINE, idempotent
    def assert_embargo_eligible(self, *, case_id, operation) -> None: ...
        # raises unless P/X/A are all clear (propose_embargo's STRICT guard)
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
  pre-store skips the case — and nothing is saved. An inline embargo whose
  `context` is not the carrying case is refused unstored: the inbox pre-store
  runs before the handler's trust checks and a first write wins, so a sender
  must not plant another case's embargo under an id that case will name.
  Extraction reduces an inline embargo to its id, so on the received side it
  is the inbox pre-store that holds the carried record before dispatch.
- **Ledger replay** — entries are applied in chain order (SYNC-14-003), and the
  CASE_MANAGER commits A's proposal before any activation that replaces it.
  Each embargo apply node — proposal, relayed Invite, Accept, Reject and
  teardown — stores the `EmbargoEvent` its entry carries before calling
  `EmbargoLifecycle` (#3915), and fails, blocking the persist (SYNC-12-001),
  when the entry names the embargo by id only and the replica lacks it.
- **The activation writers** — `accept_embargo_invite()`,
  `activate_embargo()` and the creation-time `initialize_creation_embargo()`,
  the only paths that *activate* an embargo (EM state plus `active_embargo`).
  All three compute their EP-05-001 arm through
  `EmbargoLifecycle._activation_arm()` before any write: it reads the
  activated record, and on a revision the replaced one too, so a bare id from
  an inbox (which stores only the first level of nesting: `Accept(Invite(A))`
  keeps the Invite, not A) raises `VultronNotFoundError` or
  `VultronNotAnEmbargoError` (a `VultronValidationError` that names the
  embargo id) in either `TransitionMode` and writes nothing. These
  methods live in `embargo_lifecycle/activation_arm.py`. The creation-time
  writer takes the `EmbargoEvent` itself, not an id: it stages the event
  first and stores it in the activating commit, so its read of the activated
  record is of the staged one (#4182).

So "a replica lacking the replaced embargo" is a broken invariant, not a
replication lag, and no catch-up fetch, replay-on-store trigger, or
`end_time`-in-snapshot mechanism is built for it (CONCERN-4004). Nothing would
re-drive a parked item, so there is no `DEFERRED` arm:
`RecordParticipantAcceptanceNode` reports an unreadable replaced embargo
(missing, or not an `EmbargoEvent`) as an invariant violation logged at ERROR,
and the handler reports `REFUSED` (HP-01-003). A sender-side refusal to build
an announce during sync replay is logged at ERROR too, not as a recoverable
WARNING. An unknown *accepted* embargo stays an ordinary WARNING refusal.

**`TransitionMode`**: `STRICT` enforces valid transitions and precondition
guards. A trigger runs it only in its CASE_MANAGER arm; a non-manager's trigger
runs no lifecycle write at all (EP-09-008). `OBSERVED` syncs local state
unconditionally to match the CASE_MANAGER's committed assertion (used by
received-side and ledger-replay nodes — bypasses all guards).

**P/X/A embargo-eligibility guards** (added in
[#1454](https://github.com/CERTCC/Vultron/issues/1454)): `EmbargoLifecycle`
enforces EMB-01-002, EMB-02-002, and EMB-04-002 via
`_assert_pxa_embargo_eligible()` in STRICT mode:

- `propose_embargo()` — raises when `pxa_state != CS_pxa.pxa` (any of P/X/A set)
- `accept_embargo_invite()` — raises when owner would drive EM to ACTIVE with
  P/X/A set; non-owner consent recording is not blocked
- `reject_embargo_invite()` — raises when EM is REVISE and P/X/A is set (caller
  MUST use `terminate_active_embargo()` instead)

The received-side path (`received/embargo/`) reaches `EmbargoLifecycle`
through nodes: the received Accept runs `accept_embargo_invite(OBSERVED)`
(`RecordParticipantAcceptanceNode`), the received Reject records consent through
`record_embargo_rejection` (`RecordParticipantRejectionNode`) and decides the
proposal through `RemoveFromProposedEmbargoesNode`, and the teardown replay runs
`terminate_active_embargo(OBSERVED)`.

**Late-Accept routing (EMB-17)**: when an inbound `Accept(Invite(EmbargoEvent))`
arrives after the RSVP deadline, `AcceptInviteToEmbargoOnCaseReceivedUseCase`
first commits a CASE_MANAGER-authored expiry entry (commit→effect,
`create_invite_expiry_tree`), then routes to one of three branches.
Each branch commits a synthesised entry so replicas learn the outcome
(RSH-08-004); all three factories in
`vultron/core/behaviors/embargo/expiry_tree.py` are gated on CASE_MANAGER
(BT-17-001):

- **EMB-17-001** (honour — active, matching embargo): `create_honour_late_accept_tree`
  commits an `honour_late_accept_invite_to_embargo_on_case` entry
  (`HONOUR_LATE_ACCEPT_EVENT_TYPE`), then `HonourLateAcceptNode` calls
  `honour_late_accept()` which applies `EXPIRED → SIGNATORY` directly, or
  `DECLINED → INVITED → SIGNATORY` via `honour_late_accept()` in
  `consent.py`.
  Replicas learn the outcome through `ApplyHonourLateAcceptFromLedgerNode`
  in `create_announce_log_entry_tree`.
- **EMB-17-003** (stale embargo — re-invite): `create_reinvite_stale_accepter_tree`
  stamps a fresh deadline, commits the Invite as an
  `invite_to_embargo_on_case_reinvite` entry (EMB-17-011) before it is queued,
  and `EmbargoLifecycle.record_embargo_invite()` records it on the manager.
  Replicas learn it through `ApplyEmbargoReinviteFromLedgerNode`, which records
  the same PEC `INVITE` and deadline and moves no EM state.
- **EMB-17-004** (EM `EXITED`/`NONE` — no-op): `create_noop_ledger_entry_tree`
  commits an `invite_to_embargo_on_case_expired_noop` entry; no PEC transition is
  applied (after a termination nothing is recorded, and an `EXPIRED` row
  remains `EXPIRED`).

A non-manager processing a late Accept receives `REFUSED` from the tree gate
and applies no consent change (HP-01-005, BT-17-001).
See `notes/participant-embargo-consent.md` §"Synthesised Ledger Entries" for
the full entry table and replay node inventory.

The received Invite tree (`invite_to_embargo_on_case_tree`) has two role-gated
arms (#3913, EP-09-001):
in the CASE_MANAGER's store `ProposeEmbargoLifecycleNode(proposer_id=…)` runs
`propose_embargo(STRICT)` — `NONE → PROPOSED`, `ACTIVE → REVISE`, or no move for
a counter-proposal — recording the *proposer's* consent, after a read-only
`EmStateAdmitsProposalNode` guard ahead of the commit has refused an `EXITED`
case; then `RelayEmbargoInviteToEachNode` relays the Invite to every participant
except the proposer, commits each emission and applies PEC `INVITE` where
CM-18-003 allows it. In any other store the tree stores the Invite and its
`EmbargoEvent` and answers it to the CASE_MANAGER through the response decision
(EMB-15), writing no EM or consent state (EP-09-003); the replica takes that
state from the ledger through the relay replay nodes in
`vultron/core/behaviors/embargo/nodes/relay_effect.py` (#3915, RSH-08-004).
The owner's Reject of an open proposal is decided by
`DecideRejectedEmbargoProposalNode` in both stores, `STRICT` on the CASE_MANAGER
and `OBSERVED` on replay: `reject_embargo_invite` returns EM `REVISE → ACTIVE`
(or `PROPOSED → NONE`) and forgets the proposal. EMB-01-002 and
EMB-02-002 are enforced as explicit pre-flight guards in
`InviteToEmbargoOnCaseReceivedUseCase.execute()` and
`AcceptInviteToEmbargoOnCaseReceivedUseCase.execute()` respectively (implemented
in [#1484](https://github.com/CERTCC/Vultron/issues/1484)); the refusal lives in
`vultron/core/use_cases/received/_embargo_pxa.py`. The Invite refusal stores the
Invite and the `EmbargoEvent` it carries, because the store keeps an Invite's
object by reference and the ER factory needs the proposal whole (#4104). It
answers where any Invite answer goes: the CASE_MANAGER answers the proposer, and a
participant answers the CASE_MANAGER, never a peer (EP-09-003, PCR-08-001). It sends
no ER for an Invite addressed to someone else (EP-09-010) or one naming terms the
receiver does not hold (Regime 2, ADR-0087). An Invite the receiver already
answered (`pending_embargo_proposal_index` maps its embargo to it) is skipped, so a
later P/X/A never contradicts an earlier answer. "Already stored" is not that
signal: FastAPI ingress stores the Invite before dispatch. The refusal itself
records no decision, so a repeated refusal answers twice (#4140). Moving this
refusal into the receive tree is #3872.

**A participant answers a revision on a P/X/A case with ER, never ET**
(EMB-03-003, EMB-01-002, ADR-0118). This is the one statement of the rule. A
participant that is neither the case owner nor the CASE_MANAGER and receives a
revision Invite when P/X/A is set sends ER to the CASE_MANAGER and changes no EM
state. Termination belongs to the owner, or to the CASE_MANAGER when delegated
(EP-09-003, EP-09-008, CM-24); a participant emitting ET would write shared EM
state it does not own. The ER duty binds only the addressee: every received
embargo use case first runs the door check `unaddressed_copy_refusal()`
(`vultron/core/use_cases/_helpers.py`), which refuses (HP-01-005), before any
write, an activity whose receiver is neither its sender nor in its `to`/`cc`, so
an unaddressed copy is answered by nobody.

**Auto-terminate on publication** (CS.P/X/A event): the live receive path is
`ThreatTerminationBranchNode` (`status/nodes/threat_termination.py`), under the
teardown gate of `add_case_status_tree` and `add_participant_status_tree`. It
builds `pxa_embargo_teardown_bt`, a Selector whose arms depend on the current
EM state:

- **EM ACTIVE or REVISE** → `terminate_embargo_bt` (ET + EM → EXITED). This is
  the cascade path for AC-2 of issue #1454.
- **EM PROPOSED** → `reject_proposed_embargo_bt`. EMB-16-001: continuing to
  negotiate a proposed embargo after P/X/A is set is not viable, so every open
  proposal is abandoned (EM → NONE). Only the CASE_MANAGER writes; anyone else
  writes and sends nothing (EMB-16-002; see the write gate below).
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
   settles consent when it replaces the active embargo: a *shorter* replacement
   carries every signatory over by marking the revision's row `ACCEPTED`, and
   under *longer* terms the signatories who have not accepted them have lapsed
   by derivation, with nothing written (MSM-07-005).
   `terminate_active_embargo()` clears the active embargo and writes no consent
   (MSM-07-006); an unanswered invite past its deadline moves its `INVITED` row to
   `EXPIRED` (`EXPIRE`, CM-28-004). Callers do not need to do this manually.
5. **OBSERVED mode** (received-side): pass
   `transition_mode=TransitionMode.OBSERVED` to sync local state with a remote
   assertion. EM transition guards are bypassed in OBSERVED mode; the PEC
   cascades still run, so a replica's consent records stay in step with the
   CASE_MANAGER's.
6. **PROPOSED + P/X/A**: when a CS public/exploit/attacks event fires while EM
   is PROPOSED, use `reject_proposed_embargo_bt` (not `terminate_embargo_bt`).
   `terminate_embargo_bt` requires an active embargo (`HasActiveEmbargoNode`
   guard); it fails when EM is PROPOSED. `reject_proposed_embargo_bt` calls
   `abandon_embargo_proposals()` as the CASE_MANAGER, which drops every open
   proposal and drives PROPOSED → NONE (EMB-16-001, EP-09-008).
7. **Several proposals can be open at once, and order is by expiration, not
   arrival** (EP-08, ADR-0100). See the section below before touching any
   proposal-selection code.
8. **Reading EM state inside an action node** goes through `ReadEmStateNode`
   (`vultron/core/behaviors/embargo/nodes/em_state.py`), never
   `case.current_status.em` inline (AC-1, #1474; `WriteEmStateNode` was retired
   in #2712 — writes go through the service). Call the shared
   `read_case_em_state()` helper beside it rather than wiring a
   `ReadEmStateNode` up by hand; it raises `BtNodePreconditionError` when the
   case or its state cannot be read (BT-HELPER-01, CS-22-001):

   ```python
   try:
       current_em = read_case_em_state(self.datalayer, case_id)
   except BtNodePreconditionError as exc:
       self.feedback_message = str(exc)
       return Status.FAILURE
   ```

   A refusal arm in a Selector lets the error propagate instead of catching
   it (`notes/bt-pitfalls.md` § "A Refusal Arm in a Selector Fails Toward
   'Admit'"). A node that exposes a `result_out` dict to its caller passes it
   as the third argument, and the read fills `em_before` or `error` into it.

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
- **Neither record of open proposals was fully pruned.** Nothing removed a
  decided entry from `pending_embargo_proposal_index`, and `proposed_embargoes`
  was pruned only on teardown, so a **rejected** proposal survived in both.
  Fixed by #3470: `VulnerabilityCase.discard_proposed_embargo` forgets a
  proposal in both records at once, and every decision path calls it —
  activation, the owner's `Reject` (`answers.py`), teardown and the P/X/A
  abandonment. An unpruned record is not a weaker guarantee than a
  pruned one; it is a different and wrong answer, because a decided proposal
  stays selectable.

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
  `accept_embargo_invite`, and the received `Reject(Invite)` tree and its ledger
  replay both run `DecideRejectedEmbargoProposalNode`, which acts only when the
  rejecting actor is the case owner and goes through `reject_embargo_invite` — so
  the decided proposal is forgotten and EM leaves `REVISE`/`PROPOSED` in every
  store, where a later default selection could otherwise still pick it. Termination decides *every* open proposal, not only the terminated
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
   is refused as a misrouting (EP-09-010). A revision Invite to a signatory
   changes nothing that binds it: `INVITE` lands on the revision's own row and
   the signatory keeps its `ACCEPTED` row for the active embargo (EP-09-004).
5. The owner's answer is consent *and* decision: `Accept` activates
   (`PROPOSED → ACTIVE`, or `REVISE → ACTIVE` with the EP-05-001 carry-over),
   `Reject` clears a first proposal or keeps the prior terms. The owner MAY
   decide without waiting (EP-09-005) and SHOULD wait for some answers to gauge
   consensus (EP-09-006); no quorum or vote is defined — that is actor policy,
   a call-out point.
6. Only the CASE_MANAGER evaluates invite expiry; the expiry entry is role-gated and
   replayed (CM-28-014). Replay nodes reconstruct the proposal, each relayed
   Invite, each answer and the owner's decision via `EmbargoLifecycle(OBSERVED)`
   (EP-09-007, RSH-08-004, built in #3915), which is what made the
   participant-side Invite tree gateable; the expiry replay
   (`ApplyInviteExpiryFromLedgerNode`, ADR-0118) applies the expiry entry. The
   slot table is in `notes/case-communication-model.md` § "What the
   participant and its replica do".

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

**A trigger writes shared EM state only as the CASE_MANAGER (EP-09-008).**
The five embargo triggers used to write their own local EM state before the
manager answered, then declare it; nothing corrected the write on a refusal.
Each trigger tree in `vultron/core/behaviors/embargo/trigger_tree.py` now ends
in two mutually exclusive arms built by `_by_role()`
(`create_case_manager_gated_tree` beside
`create_participant_replica_gated_tree`, BT-17-001):

- **As the CASE_MANAGER** the decision is canonical: the
  `*EmbargoLifecycleNode` write runs `STRICT`, then `CommitEmbargoDecisionNode`
  (`nodes/manager_commit.py`) builds the decision activity, commits its sealed
  blob as a ledger entry the announce slots replay, and only then queues it
  (#4085; before, the manager's own decisions committed nothing and replicas
  never moved). Nothing is addressed to the manager itself (CLP-10-001): an
  `Accept`/`Reject` is addressed to nobody and only committed; its own proposal
  is committed and then relayed as one `Invite` per other participant
  (EP-09-002), which `ApplyEmbargoProposalFromLedgerNode` also replays as a
  relayed Invite because it is self-attributed; its teardown goes to every
  other participant (EMB-19-001, #4112). `EmitCaseStatusUpdateNode` follows,
  because RSH-04-002 requires a `CaseStatus` write after every EM mutation and
  its duplicate-entry exemption covers only received trees (see "RSH-04-002 on
  the relay trees" below). No replica apply node reads that entry for EM: the
  decision entry carries the transition (RSH-08-004). The ask arm makes no EM
  mutation, so it writes no `CaseStatus`.
- **As anyone else** the tree writes no EM state and declares none. It queues
  the activity to the CASE_MANAGER through `sender_side_bt` and writes its id to
  `result_out[ASSERTED_ACTIVITY_KEY]`. `SvcEmbargoTriggerBase` records it with
  `record_pending_assertion()` (SYNC-11-002), the helper the note trigger also
  uses, keyed by a `subject_id` (the terms, the answered proposal, the ended
  embargo) so a repeat inside the window is suppressed before the tree runs
  and reported with no activity. The replica moves on the announced commit
  (SYNC-11-003 clears the entry); a refused proposal is never committed, so
  the CASE_MANAGER's `Reject` of it closes the entry instead
  (`close_refused_embargo_proposal`).

The receive-side cascade that ends an embargo (`ThreatTerminationBranchNode`)
reaches the same `terminate_embargo_bt`, so it too tears down only at the
CASE_MANAGER and a non-manager receiver asks. That ask is a pending assertion
too: no use case wraps the cascade, so `ask_case_manager_to_terminate_once`
puts `TeardownAskPendingNode` ahead of `SendTerminateEmbargoActivityNode`,
whose `_on_queued` hook records the queued ask with the same event type and
the ended embargo as subject. A repeat P/X/A signal inside the window queues
no second ask, and the trigger and the cascade suppress each other (#4147).
It builds its teardown with `pxa_embargo_teardown_bt`: terminate an active
embargo, else abandon the open proposals with `reject_proposed_embargo_bt`
(EMB-16-001, #4145). Ratchet:
`test/architecture/test_embargo_trigger_writes_are_case_manager_gated.py`.

**A replica never asks for a teardown the CASE_MANAGER declared** (RSH-03-004,
issue #4149). The manager tears down on its own P/X/A detection and declares the
new status, and the declaration can reach a replica before the teardown
entries do. `ThreatTerminationBranchNode` is given the status's sender, and
`_DeclaredByCaseManagerNode` skips the branch when that sender holds the
CASE_MANAGER role and is not the executing actor: the replica waits for the
entry instead of asking for what is already done. The skip decides *who*
carries out the teardown, not *whether* it is allowed: it is not a sender-role
authorization gate (RSH-03-002), and a status from anyone else still runs the
branch. For the same reason `PxaEmInvariantDiagnosticNode` posts no CSB-18
Note for a CASE_MANAGER-declared status at a replica: the P/X/A–EM gap it
would report is the one the manager's entry is about to close.

**The P/X/A abandonment decides every open proposal (EMB-16-001, #4131).**
`P → N` leaves nothing open, so the earliest-expiring order of EP-08-002 does
not apply: the CASE_MANAGER drops every proposal
(`abandon_embargo_proposals`, STRICT) and commits one
`Reject(Invite(EmbargoEvent))` per proposal under the
`reject_invite_to_embargo_on_case_abandoned` event type (MSM-02-006). The
entry is addressed to nobody: every replica learns it from the ledger, whose
`EmbargoAbandonment` announce slot drops the proposal in OBSERVED mode
(`ApplyEmbargoAbandonmentFromLedgerNode`). The replica does not repeat the
owner check a received `Reject` makes: the entry is the manager's decision,
as a teardown already decides every open proposal (EP-08-004). Only the
manager reads each proposal's Invite from `pending_embargo_proposal_index`,
and a proposal with none fails its run closed before anything moves.

**A non-manager sends no ER for the abandonment (EMB-16-002, #4148).** Only
the case owner, or the CASE_MANAGER it delegates to, decides to abandon the
case's open proposals. A non-manager's P/X/A signal already reaches the
CASE_MANAGER as its status declaration, and the manager abandons on that
detection. A `Reject(Invite)` sent as the abandonment would arrive as an
ordinary ER, which the manager reads as that participant declining the
proposal (MSM-07-004) — an abandonment the participant had no standing to
make — and which would not make the manager abandon anything. So the
non-manager arm (`LeaveAbandonmentToCaseManagerNode`) writes and sends
nothing, and the
participant's replica moves when the manager's entry is replayed. EMB-16-001's
"emit ER" is met by the manager's committed entries, as EP-09-009 makes the
manager's commit the EK.

**Two rules, side by side.** EMB-16-002 covers the abandonment of proposals
already open on the case; EMB-01-002 covers what a participant *receives*. A
proposal, Invite or revision that reaches a participant while it believes the
case is at P, X or A is still answered with ER by that participant, manager or
not: that ER is its own answer to something addressed to it, not an
abandonment on the case's behalf.
Participant self-status (RM) keeps its local write — the participant is the
authority on its own progress. ADR-0108 was amended to match.

**The role is never unfilled.** Both creation paths register a `CASE_MANAGER`
holder at birth and delegation hands it on (CM-24-006). No "no manager" arm
belongs in any embargo tree; a resolver that finds nobody fails.

**Only the CASE_MANAGER records an answer, and only one it can apply.** The
received `Accept`/`Reject(Invite(EmbargoEvent))` trees put their effects
behind `create_case_manager_gated_tree`; a participant handed an answer
directly reports `REFUSED` through `not_case_manager_refusal()` and writes
nothing (BT-17-001, HP-01-005). A `Reject` naming an embargo that is neither
active nor open — a late answer to a decided revision — is refused by a
read-only guard *before* the guarded commit (`IsRejectableEmbargoNode`). Once
committed, an entry whose replica apply node fails blocks its persist
(SYNC-12-001) and every later entry buffers behind it (SYNC-14-001), so a
refusal the manager makes after its commit stalls every replica. The replay
of a rejection of an embargo the replica no longer holds is a no-op for the
same reason.

**The owner's Reject decides one proposal, not all of them.** With several
open (EP-08-001), it forgets the one it names (EP-08-003) and EM stays
`PROPOSED`/`REVISE` while another is open. When it rejects the last open
revision after P/X/A is set, the case does not return to the prior terms: the
manager runs the terminate path (`terminate_embargo_bt`, ET), as
`ThreatTerminationBranchNode` does, and replicas follow its
`Remove(EmbargoEvent)` (EMB-04-002).

**RSH-04-002 on the relay trees.** These received trees add no
`EmitCaseStatusUpdateNode`. Their guarded commit records the activity that
caused the transition, and its relay apply node replays that transition in
every replica (EP-09-007, RSH-08-004, ADR-0113), so the committed entry *is*
the canonical ledger write. A second `CaseStatus` entry would duplicate it.
RSH-04-002's text says so (#4103).

The creation-time revision from shortest-wins follows the same relay
(EP-04-011) — see `notes/embargo-default-semantics.md`.

## Who May Send Each Embargo Message (ADR-0115, HP-01-006)

A received embargo activity is an assertion about its sender's standing, so
each handler asks who sent it before it writes, sends or commits anything.
The rule depends on who receives it, because the embargo is adjudicated at the
CASE_MANAGER and a participant takes case state from the CASE_MANAGER alone
(PCR-03-001, PCR-08-001):

| Message | At the CASE_MANAGER | At any other replica |
|---|---|---|
| `Invite(EmbargoEvent)` | an active participant (CM-10-004) | the CASE_MANAGER (EP-09-003) |
| `Accept` / `Reject(Invite)` | the recorded Invite's sole `to` recipient (EP-09-010) | the same; the answer is then refused by the role gate |
| `Create` / `Add` / `Remove(EmbargoEvent)` | the Case Owner, or the CASE_MANAGER itself | the CASE_MANAGER |
| `Announce(EmbargoEvent)` | the CASE_MANAGER | the CASE_MANAGER |

The two shared nodes are `SenderMayAssertEmbargoNode` and `SenderIsInviteeNode`
in `vultron/core/behaviors/sender_entitlement.py`.
Two things are easy to get wrong:

- **The invitee comes from the store, never from the reply.**
  `SenderIsInviteeNode` reads the Invite this store recorded, so a reply that
  embeds a doctored copy of its Invite cannot name itself the invitee.
  An Invite this store never recorded names no invitee and is refused.
- **A handler that writes before its tree runs checks first.**
  Accept (the P/X/A rejection, the expiry commit), Reject (closing the pending
  ask), Invite (the P/X/A rejection), Create and Announce (no tree) run the same
  guard through `sender_refusal()` ahead of that write.
  The tree carries the guard as well, in the factory's sender stage.

The specs do not say who may send `Create`, `Add` or `Remove(EmbargoEvent)` at
the CASE_MANAGER.
The rule above follows EP-09-005 (the owner decides the embargo) and the
termination rule in § "A participant answers a revision on a P/X/A case with
ER, never ET" (the owner, or the CASE_MANAGER when delegated).
