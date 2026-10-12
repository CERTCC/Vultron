---
source: NOTES-embargo-lifecycle--current-architecture-implemented
timestamp: '2026-10-12T19:33:15.875923+00:00'
title: Current Architecture (Implemented)
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered (#538, #746, #747, #1454, #1484, #1892, #3913, #3915, #4140); interface copy, node tour and fix history removed; live rules restated as short guidance sections
**Superseded by:** vultron/core/services/embargo_lifecycle/; vultron/core/behaviors/embargo/; EMB-18, EMB-17, EMB-16, CM-23-014; notes/embargo-lifecycle.md

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
        self, *, case_id, embargo_id, actor_id
    ) -> EmbargoLifecycleResult: ...  # the sender's consent; EM unchanged
    def reject_embargo_proposal(
        self, *, case_id, embargo_id, actor_id=None, transition_mode=STRICT
    ) -> EmbargoLifecycleResult: ...  # the owner's REJECT; no consent
    def terminate_active_embargo(
        self, *, case_id, reason, actor_id, transition_mode=STRICT
    ) -> EmbargoLifecycleResult: ...
    def activate_embargo(
        self, *, case_id, embargo_id, actor_id=None, transition_mode=STRICT
    ) -> EmbargoLifecycleResult: ...  # the owner's ACTIVATE; owner AGREE
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

The answers to an Invite and the case owner's decision on a proposal are
separate operations, because they are separate messages (ADR-0122):
`accept_embargo_invite` and `record_embargo_rejection` record a sender's own
consent to an `Accept`/`Reject(Invite(EmbargoEvent))` — the owner's included —
and move no register entry (MSM-07-003, MSM-07-004); `activate_embargo` and
`reject_embargo_proposal` apply the owner's `Accept`/`Reject(EmbargoEvent,
target=Case)` (MSM-07-008, MSM-07-009). No operation branches on whether the
sender is the owner. The received `Reject(Invite(EmbargoEvent))` tree and the
trigger both reach `record_embargo_rejection`, through
`RecordParticipantRejectionNode` and `RejectEmbargoLifecycleNode`, so both
sides apply one MSM-07-004 rule.

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
  (`HoldCarriedEmbargoNode`) and the inbox pre-store of an inbound case. It
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
- **The activation writers** — `activate_embargo()` (the owner's
  `Accept(EmbargoEvent, target=Case)`) and the creation-time
  `initialize_creation_embargo()`, the only paths that *activate* an embargo
  (a register `ACTIVATE` step). Both compute their EP-05-001 arm through
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
re-drive a parked item, so there is no `DEFERRED` arm: the owner's activation
(`ActivateEmbargoLifecycleNode`, and `SetEmbargoActiveNode` on replay) fails on
an unreadable replaced embargo (missing, or not an `EmbargoEvent`), and the
handler reports `REFUSED` (HP-01-003). Recording consent reads no embargo
record, so `RecordParticipantAcceptanceNode` has no such failure (ADR-0122). A sender-side refusal to build
an announce during sync replay is logged at ERROR too, not as a recoverable
WARNING. An unknown *accepted* embargo stays an ordinary WARNING refusal.

**`TransitionMode`**: `STRICT` raises on a refused register step and enforces
the precondition guards. A trigger runs it only in its CASE_MANAGER arm; a
non-manager's trigger runs no lifecycle write at all (EP-09-008). `OBSERVED`
follows the CASE_MANAGER's committed assertion (received-side and ledger-replay
nodes): it skips the P/X/A guards, records a proposal a replica never saw before
activating it, and logs and skips a step the register refuses — it never forces
the register into a state its rules refuse.

**P/X/A embargo-eligibility guards** (added in
[#1454](https://github.com/CERTCC/Vultron/issues/1454)): `EmbargoLifecycle`
enforces EMB-01-002, EMB-02-002, and EMB-04-002 via
`_assert_pxa_embargo_eligible()` in STRICT mode:

- `propose_embargo()` — raises when `pxa_state != CS_pxa.pxa` (any of P/X/A set)
- `activate_embargo()` — raises when P/X/A is set; consent recording by
  `accept_embargo_invite()` is never blocked
- `reject_embargo_proposal()` — raises when it would return a `REVISE` case to
  the prior terms with P/X/A set (caller MUST use `terminate_active_embargo()`
  instead, EMB-04-002). This one is not skipped in `OBSERVED` mode: the replay
  changes nothing, because the CASE_MANAGER answered that Reject with ET and
  the termination entry that follows cancels the revision. The CASE_MANAGER
  and every replica end with it `CANCELLED`, and none returns to the prior
  terms (ADR-0124, #4364).

`activate_embargo()` also refuses, in either mode, an owner whose row for the
proposal is `DECLINED`: activation records the owner's `AGREE`, which
`DECLINED` refuses, so the owner is invited again first (ADR-0122). The
received owner-decision trees check both refusals with read-only guards ahead
of the commit (`OwnerMayActivateEmbargoNode`), because a replica replays the
committed activation `OBSERVED`, which does not re-check P/X/A.

The received-side path (`received/embargo/`) reaches `EmbargoLifecycle`
through nodes: the received `Accept(Invite)` records consent through
`accept_embargo_invite` (`RecordParticipantAcceptanceNode`), the received
`Reject(Invite)` through `record_embargo_rejection`
(`RecordParticipantRejectionNode`); the owner's `Accept(EmbargoEvent)` runs
`activate_embargo` (`ActivateEmbargoLifecycleNode`) and its
`Reject(EmbargoEvent)` runs `reject_embargo_proposal`
(`DecideRejectedEmbargoProposalNode`), both in `owner_decision_tree.py`; the
teardown replay runs `terminate_active_embargo(OBSERVED)`.

**Late-Accept routing (EMB-17)**: when an inbound `Accept(Invite(EmbargoEvent))`
answers a closed invitation — its RSVP deadline passed, or its row is already
`TIMED_OUT` or `DECLINED` (the row drops its deadline when it leaves `INVITED`,
so the state is what says the invitation closed) —
`AcceptInviteToEmbargoOnCaseReceivedUseCase` first commits a CASE_MANAGER-authored
expiry entry when the row still needs `TIME_OUT` (commit→effect,
`create_invite_expiry_tree`), then routes to one of three branches.
Each branch commits a synthesised entry so replicas learn the outcome
(RSH-08-004); all three factories in
`vultron/core/behaviors/embargo/expiry_tree.py` are gated on CASE_MANAGER
(BT-17-001):

- **EMB-17-001** (honour — active, matching embargo): `create_honour_late_accept_tree`
  commits an `honour_late_accept_invite_to_embargo_on_case` entry
  (`HONOUR_LATE_ACCEPT_EVENT_TYPE`), then `HonourLateAcceptNode` calls
  `honour_late_accept()` which applies `TIMED_OUT → AGREED` directly, or
  `DECLINED → INVITED → AGREED` via `honour_late_accept()` in
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
  applied (after a termination every row is frozen, and a `TIMED_OUT` row
  remains `TIMED_OUT`).

A non-manager processing a late Accept receives `REFUSED` from the tree gate
and applies no consent change (HP-01-005, BT-17-001).

**Settle on owner close (CM-23-014)**: after close an Invite can only expire,
so the owner-close sequence does not wait for any RSVP deadline.
`ExpirePendingInvitesOnCloseNode` runs between the CASE_MANAGER's `RM.CLOSED`
entry and `case_fully_closed`. For each pair that
`EmbargoLifecycle.pending_invitations()` returns (an `INVITED` row on an open
register entry), it runs the late-Accept path's own commit → effect subtree,
`create_commit_and_record_expiry_tree`. So the entry type, the transition and
the replica replay node (`ApplyInviteExpiryFromLedgerNode`) are one copy. A row
on a final entry is frozen and is not pending, which covers a stub invitee's
row on the embargo that the close already required to end. The entry names the
last Invite the ledger records for that invitee and embargo. Its `published`
is the CASE_MANAGER's clock, because the invitee sent nothing (the named
exception in `notes/case-ledger-authority.md`, trap 3). Recording is
best-effort, as for the `RM.CLOSED` entry: a failure here must not cost the
case its `case_fully_closed`.
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
The owner's `Reject(EmbargoEvent, target=Case)` is decided by
`DecideRejectedEmbargoProposalNode`, `STRICT` on the CASE_MANAGER and
`OBSERVED` on replay (the `EmbargoProposalRejection` slot):
`reject_embargo_proposal` returns EM `REVISE → ACTIVE` (or `PROPOSED → NONE`),
or leaves it in place while another proposal is open (EMB-18-005), and rejects the proposal, except for the last revision with P/X/A set, which
it leaves to the ET that follows (EMB-04-002); the owner's
`Accept(EmbargoEvent, target=Case)` is replayed by the `EmbargoActivation`
slot (ADR-0122). EMB-01-002 and
EMB-02-002 are enforced as explicit pre-flight guards in
`InviteToEmbargoOnCaseReceivedUseCase.execute()` and
`AcceptInviteToEmbargoOnCaseReceivedUseCase.execute()` respectively (implemented
in [#1484](https://github.com/CERTCC/Vultron/issues/1484)); the refusal lives in
`vultron/core/use_cases/received/_embargo_pxa.py`, which runs
`RefuseEmbargoInviteBT` (`vultron/core/behaviors/embargo/refusal_tree.py`). The
Invite refusal stores the Invite and the `EmbargoEvent` it carries, because the
store keeps an Invite's object by reference and the ER factory needs the
proposal (#4104). It answers where any Invite answer goes: the CASE_MANAGER
answers the proposer, and a participant answers the CASE_MANAGER, never a peer
(EP-09-003, PCR-08-001). It sends no ER for an Invite addressed to someone else
(EP-09-010). An Invite that names its terms by URI only is answered all the
same: the ER names the Invite by id and needs no terms (ADR-0123, #4181). An
Invite the receiver already answered (`pending_embargo_proposal_index` maps its
embargo to it) is skipped, so a later P/X/A never contradicts an earlier answer.
"Already stored" is not that signal: FastAPI ingress stores the Invite before
dispatch.

The ER is itself the record of the refusal (#4140). Its id derives from the
rejecting actor and the Invite (`TriggerActivityPort.requeue_embargo_refusal`),
and a node of the tree queues it, not `execute()` (CLP-10-020), so a repeated
delivery of the Invite or of its Accept finds the ER sent and is `SKIPPED`
(HP-01-003, CLP-13-001). The sealed ER is written before the queue append, so
the latch is ahead of the work it stands for (ID-04-005): an ER sealed but no
longer pending is queued again under its own id, which the receiver
deduplicates, rather than read as delivered. An Invite that breaks a shape rule
is a different kind of fault: one naming no `to` recipient or several
(EP-09-010), or no embargo, is received but not understood and is answered with
`Create(ProcessingFault)`, not ER (MSM-05-001).

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

**Embargo-ending notices to unreached signatories** (CM-31-009, CM-31-010):
every CASE_MANAGER path that terminates or replaces the active embargo brackets
its EM write with `embargo_ending_notice_nodes` (`nodes/ending_notice.py`,
issue 4083), which sends a direct ET or `Announce(EmbargoEvent)` to each bound
signatory the ledger no longer reaches.
See `notes/case-joining.md` § "Removal and reinstatement".

**Auto-terminate on publication** (CS.P/X/A event): the live receive path is
`ThreatTerminationBranchNode` (`status/nodes/threat_termination.py`), under the
teardown gate of `add_case_status_tree` and `add_participant_status_tree`. It
builds `pxa_embargo_teardown_bt`, a Selector whose arms depend on the current
EM state:

- **EM ACTIVE or REVISE** → `terminate_embargo_bt` (ET + EM → EXITED). This is
  the cascade path for AC-2 of issue #1454.
- **EM PROPOSED** → `reject_proposed_embargo_bt`. EMB-16-001: continuing to
  negotiate a proposed embargo after P/X/A is set is not viable, so every open
  proposal is cancelled (EM derives NONE). Only the CASE_MANAGER writes; anyone else
  writes and sends nothing (EMB-16-002; see the write gate below).
- **EM NONE or EXITED** → skip (nothing to tear down).

Prior to the fix in issue #1892, the skip condition used
`case.active_embargo is None` to detect "no embargo", which silently bypassed
the PROPOSED arm — `active_embargo` is always None when EM is PROPOSED because
the embargo has not yet been activated. The fix checks EM state directly.

Trigger use cases are thin orchestrators: resolve actors/cases → call
`EmbargoLifecycle` → build and send the outbound activity.
BT behaviors use `ProposeEmbargoLifecycleNode`, `AcceptEmbargoLifecycleNode`,
`RejectEmbargoLifecycleNode`, `ActivateEmbargoLifecycleNode`,
`RejectEmbargoProposalLifecycleNode` and `TerminateEmbargoLifecycleNode`, which
all catch `VultronError` and return `Status.FAILURE`. The accept and reject
triggers pick by actor: a case owner's `accept-embargo` and `reject-embargo`
send its decision for the case (`activate_embargo_trigger_bt`,
`reject_embargo_proposal_trigger_bt`), anyone else's its consent (ADR-0122).

---
