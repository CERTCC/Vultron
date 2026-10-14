---
title: Embargo Lifecycle — Architecture and Implementation Notes
status: active
kind: guidance
description: >
  Rules for changing embargo state: the embargo register from which EM is
  derived, changed only by EmbargoLifecycle one checked step at a time along an
  EM transition (ADR-0122, ADR-0130); consent versus owner decision; STRICT
  versus OBSERVED and the P/X/A guards; the invariant that a case never names
  an embargo its store cannot read (EMB-18-003); late Accepts, expiry and the
  owner-close settle step (EMB-17, CM-23-014); P/X/A refusal and teardown
  (EMB-01-002, EMB-16); earliest-expiration resolution of open proposals
  (EP-08); the relay through the CASE_MANAGER and its trigger write gate
  (EP-09, ADR-0113); and who may send each embargo message (ADR-0115).
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
  - specs/idempotency.yaml
  - specs/status-dimension-objects.yaml
related_notes:
  - notes/embargo-default-semantics.md
  - notes/case-state-model.md
  - notes/bt-integration.md
  - notes/bt-pitfalls.md
  - notes/participant-embargo-consent.md
  - notes/case-communication-model.md
  - notes/case-ledger-authority.md
  - notes/call-out-configuration.md
  - notes/activitystreams-semantics.md
  - notes/received-status-authorization.md
  - notes/protocol-asks.md
  - notes/case-joining.md
  - notes/status-dimension-objects.md
relevant_packages:
  - vultron/core/states/em.py
  - vultron/core/states/embargo_register.py
  - vultron/core/models/embargo_register.py
  - vultron/core/services/embargo_lifecycle/
  - vultron/core/services/carried_embargo.py
  - vultron/core/behaviors/embargo/
  - vultron/core/models/pending_assertion.py
  - vultron/core/use_cases/triggers/embargo.py
  - vultron/core/use_cases/received/embargo/
---

# Embargo Lifecycle — Architecture and Implementation Notes

The reader-facing explanation is
`docs/topics/behavior_logic/use-cases/embargo-lifecycle.md`. Consent rows are in
`notes/participant-embargo-consent.md`; the creation-time embargo is in
`notes/embargo-default-semantics.md`.

---

## Background

An embargo operation touches two records:

1. **The embargo register** (`VulnerabilityCase.embargo_register`) — one entry
   per embargo ever proposed, appended and never removed. EM is *derived* from
   it (`case.em_state`). `active_embargo`, `active_embargo_id` and
   `proposed_embargo_ids` are views of its `ACTIVE` and `PROPOSED` entries.
2. **The consent rows** (`CaseParticipant.embargo_consents`) — one per
   participant per register entry (ADR-0122). "Signatory" and "lapsed" are read
   from the rows, never stored.

A correct operation changes both consistently; EM and the views follow.

---

## The Embargo Register and the Derived EM (ADR-0122)

Statuses and triggers are in `vultron/core/states/embargo_register.py`.

- **Every change is one checked step** — the whole change one protocol event
  causes — applied by `apply_register_step()`. A refused step raises
  `VultronInvalidStateTransitionError` naming every broken rule (EH-07-001) and
  leaves the register unchanged. Apply a step to a case only through
  `VulnerabilityCase.apply_embargo_register_step` and its wrappers: they also
  prune `pending_embargo_proposal_index` (EP-08-003) and stamp EM onto the
  current `CaseStatus`.
- **`derive_em()` reads EM from the statuses**, so rejecting one of two open
  proposals leaves EM `PROPOSED` (or `REVISE`), and a case that has had an
  embargo in force never returns to `NONE` or `PROPOSED`.
- **The EM state machine still governs EM (ADR-0130).** Each step names an EM
  trigger, and EM before and after MUST be one of that trigger's transitions
  (EMB-18-005). The table is `EM_TRANSITIONS` in `vultron/core/states/em.py`
  (`is_em_transition()`; `create_em_machine()` / `em_transition_rows()` for
  tools). `apply_register_step()` names the step's EM trigger
  (`register_step_em_trigger()`; none or several is refused) and refuses a move
  not in the table (`em_move_violations()`, EMB-18-006); the check is in the
  step, so the CASE_MANAGER and every replica apply it alike. With several
  proposals open, `reject` and `accept` self-loop, and activating one proposal
  leaves the others open as revisions.
- **`CaseStatus.em` is a frozen stamped copy.** Core reads `case.em_state`,
  never the copy. `append_case_status(em_state=...)` is refused, and a received
  `Add(CaseStatus)` whose EM differs has its EM refused and the case's carried
  forward (RSH-05-023, SDO-03-006).
- **A termination records what and why (ADR-0122, EMB-13-004).** The what
  (`TerminationReason`: `END_TIME_REACHED` or `EARLY`) is the `Remove`'s
  `content`, parsed at the edge (`termination_reason_from_content()`); the why
  is a structured cause (`vultron/core/models/embargo_termination.py`), so far
  only `ThreatSignalCause` naming `P`/`X`/`A`. Both sit on the `TERMINATED`
  entry as one `EmbargoTermination`, required there and refused elsewhere. The
  cascades pass `ThreatSignalTermination(signals=...)`: the signals of the
  triggering status, or, when unknown at build time, the case's PXA at the
  write. Never put the why on the `Remove`: a replica that replays it
  records only the what, until #4294 copies whole entries (a case snapshot's
  `embargoRegister` already carries the entry, cause included). Read the
  recorded what back from the register (`case.embargo_termination`) when
  building the CASE_MANAGER's `Remove` and the CM-31-009 notices, so the wire
  and the entry cannot disagree. A `Remove` naming an embargo not in force
  changes nothing.
- **End-time termination is one idempotent path (EMB-13-003).**
  `end_embargo_at_end_time_bt` (`behaviors/embargo/end_time_tree.py`) answers
  an already-`EXITED` case as done and otherwise runs `terminate_embargo_bt`
  with `END_TIME_REACHED`. The CASE_MANAGER's lazy check is a `CaseUpkeep`
  hook (`end_time_case_upkeep`) that the composition roots install on the
  inbox and trigger dispatchers, so it runs before each activity or trigger
  for a case; the dispatchers know only the hook's shape. A Sentinel reaches
  the path through the terminate trigger with `reason=END_TIME_REACHED`. That
  trigger's registry row sets `runs_case_upkeep=False`: it takes the end-time
  path itself once the end time has passed, an `EARLY` request included, so
  the lazy check never pre-empts the answer it owes. `termination_timing_violations()` refuses an
  `END_TIME_REACHED` claimed before the end time — in the trigger's
  `_prepare`, the lifecycle, the received tree's guard
  (`TerminationIsTimelyNode`, before the commit) and replica replay.

---

## Consent and Decision Are Separate Operations

An answer to an Invite and the owner's decision on a proposal are separate
messages, so they are separate `EmbargoLifecycle` operations (ADR-0122):

- `accept_embargo_invite` / `record_embargo_rejection` record a sender's own
  consent to `Accept`/`Reject(Invite(EmbargoEvent))` — the owner's included —
  and move no register entry (MSM-07-003, MSM-07-004).
- `activate_embargo` / `reject_embargo_proposal` apply the owner's
  `Accept`/`Reject(EmbargoEvent, target=Case)` (MSM-07-008, MSM-07-009).
- No operation branches on whether the sender is the owner. The accept and
  reject triggers pick by actor: an owner sends its decision, anyone else its
  consent.
- An owner whose row is `DECLINED` may still activate: activating is the
  owner changing its answer, so its row moves straight to `AGREED`, in either
  mode, with one ledger entry (MSM-07-008). The received owner-decision trees
  check P/X/A with a read-only guard ahead of the commit
  (`OwnerMayActivateEmbargoNode`), because replay runs `OBSERVED` and does not
  re-check.
- A repeat of a recorded Accept or Reject is `SKIPPED` before the commit
  (`EmbargoAnswerNotRecordedNode`, CM-13-005); a `DECLINED` actor's Reject of
  an unknown embargo stays `REFUSED` (HP-01-003). An Accept after a Reject is
  a change of answer and moves the row straight to `AGREED` (CM-18-003).

## TransitionMode and the P/X/A Guards

- **`STRICT`** raises on a refused step and enforces the P/X/A guards. Only a
  trigger's CASE_MANAGER arm runs it (EP-09-008).
- **`OBSERVED`** follows the CASE_MANAGER's committed assertion (received and
  replay nodes): it skips the P/X/A guards, records a proposal a replica never
  saw before activating it, and logs and skips a refused step — it never forces
  the register into a state its rules refuse.
- **P/X/A guards** (EMB-01-002, EMB-02-002, EMB-04-002): `propose_embargo()` and
  `activate_embargo()` raise when any of P/X/A is set; consent recording is
  never blocked. `reject_embargo_proposal()` raises when it would return a
  `REVISE` case to the prior terms with P/X/A set — the correct path is
  `terminate_active_embargo()`. That guard holds in `OBSERVED` too, so manager
  and replicas both end with the revision `CANCELLED` (#4364).

## A Case Never Points at an Embargo Its Store Cannot Read (EMB-18-003)

The EP-05-001 comparison reads the revised and the replaced embargo, so every
path that writes `active_embargo` must hold the record first. A replica lacking
the replaced embargo is a broken invariant, not replication lag: build no
catch-up fetch or deferral, refuse instead.

- **Seeding.** A sender carries `active_embargo` inline in every outbound case
  and refuses to build the activity if its own store cannot read it. Every
  receiving writer calls `store_carried_embargo()`
  (`vultron/core/services/carried_embargo.py`) before saving the case; a case
  naming an unreadable embargo is refused and nothing is saved. An inline
  embargo whose `context` is not the carrying case is refused unstored, because
  the inbox pre-store runs before trust checks and a first write wins.
- **Ledger replay.** Each embargo apply node stores the `EmbargoEvent` its entry
  carries before calling `EmbargoLifecycle`, and fails (blocking the persist,
  SYNC-12-001) when the entry names it by id only and the replica lacks it.
- **Activation.** `activate_embargo()` and `initialize_creation_embargo()` read
  the activated record, and on a revision the replaced one, through
  `_activation_arm()` before any write, raising in either mode. The owner's
  activation then reports `REFUSED` (HP-01-003). Recording consent reads no
  embargo record and has no such failure.

## Late Accepts and Expiry (EMB-17, CM-23-014)

- **A late `Accept(Invite(EmbargoEvent))`** — deadline passed, or row already
  `TIMED_OUT`/`DECLINED` — first commits a CASE_MANAGER-authored expiry entry
  if the row still needs `TIME_OUT`, then routes to honour (EMB-17-001),
  re-invite (EMB-17-003) or no-op (EMB-17-004). Each branch commits an entry so
  replicas learn the outcome (RSH-08-004), and every factory in
  `vultron/core/behaviors/embargo/expiry_tree.py` is CASE_MANAGER-gated; a
  non-manager gets `REFUSED` and changes no consent (BT-17-001). The outcome
  table is in `notes/participant-embargo-consent.md` § "Expiry is lazy, and
  only the CASE_MANAGER's".
- **Owner close settles pending Invites without waiting.** After close an Invite
  can only expire, so `ExpirePendingInvitesOnCloseNode` runs between the
  CASE_MANAGER's `RM.CLOSED` entry and `case_fully_closed`, reusing the
  late-Accept expiry subtree for each pending invitation. Its `published` is the
  CASE_MANAGER's clock, because the invitee sent nothing. Each expiry commits
  before it writes the consent row, so a refused one writes nothing; it is
  logged and the close goes on.

## Refusing an Invite at P/X/A (EMB-01-002)

- The P/X/A refusal of a received Invite runs `RefuseEmbargoInviteBT`
  (`vultron/core/behaviors/embargo/refusal_tree.py`). It stores the Invite and
  its `EmbargoEvent` first (the ER factory needs the proposal) and answers where
  any Invite answer goes: the CASE_MANAGER answers the proposer, a participant
  answers the CASE_MANAGER, never a peer (PCR-08-001). An Invite naming its
  terms by URI only is still answered (ADR-0123).
- **Skip an Invite already answered** (`pending_embargo_proposal_index` maps its
  embargo to it), so a later P/X/A never contradicts an earlier answer.
  "Already stored" is not that signal: ingress stores the Invite before
  dispatch.
- **The ER is its own record** (ADR-0123). Its id derives from the rejecting
  actor and the Invite, a tree node queues it (CLP-10-020), and the sealed ER is
  written before the queue append (ID-04-005), so a redelivery is `SKIPPED`.
- An Invite naming no `to` recipient, several, or no embargo is answered with
  `Create(ProcessingFault)`, not ER (EP-09-010, MSM-05-001).

**A participant answers a revision on a P/X/A case with ER, never ET**
(EMB-03-003, ADR-0118). Termination belongs to the owner, or to the
CASE_MANAGER when delegated (EP-09-008); a participant's ET would write shared
EM state it does not own. The duty binds only the addressee: every received
embargo use case first runs `unaddressed_copy_refusal()`
(`vultron/core/use_cases/_helpers.py`), so an unaddressed copy is answered by
nobody.

## P/X/A Teardown

The live receive path is `ThreatTerminationBranchNode`, which builds
`pxa_embargo_teardown_bt` with arms keyed on **EM state**, never on
`case.active_embargo` (which is `None` while EM is `PROPOSED`, #1892):

- **`ACTIVE` or `REVISE`** → `terminate_embargo_bt` (ET, EM → `EXITED`).
- **`PROPOSED`** → `reject_proposed_embargo_bt`, which cancels every open
  proposal (EMB-16-001). `terminate_embargo_bt` would fail here: it requires an
  active embargo.
- **`NONE` or `EXITED`** → skip.

Every CASE_MANAGER path that terminates or replaces the active embargo brackets
its EM write with `embargo_ending_notice_nodes`, which sends an ending notice
to each bound signatory the ledger no longer reaches (CM-31-009; see
`notes/case-joining.md` § "Removal and reinstatement").

---

## Guidance for Agents

1. **Always use `EmbargoLifecycle`** (`vultron/core/services/embargo_lifecycle/`).
   BT nodes MUST NOT apply a register step, assign `case.current_status.em`, and
   `dl.save(case)` themselves (EMB-18-001). A refused step raises or fails the
   node without a write (EMB-18-002). Lifecycle nodes catch `VultronError` and
   return `FAILURE`; triggers are thin orchestrators over the service.
2. **On `VultronInvalidStateTransitionError` from a P/X/A guard**, the case is no
   longer embargo-eligible: do not retry; emit ER to the proposer.
3. **Consent cascades are automatic.** `propose_embargo()` changes no consent
   except recording the proposer's (ADR-0093). `activate_embargo()` records the
   owner's agreement; a *shorter* replacement carries every signatory over
   (`CARRY_OVER`), and under *longer* terms non-agreeing signatories lapse by
   derivation (MSM-07-005). `terminate_active_embargo()` cancels every open
   proposal and writes no consent (MSM-07-006). Callers do none of this by hand.
4. **Received side passes `transition_mode=TransitionMode.OBSERVED`**; the
   consent cascades still run, so replica rows stay in step with the manager's.
5. **Several proposals can be open; order is by expiration, not arrival** (EP-08,
   ADR-0100). Read the next section before touching proposal selection.
6. **Read EM in an action node through `read_case_em_state()`** beside
   `ReadEmStateNode` (`vultron/core/behaviors/embargo/nodes/em_state.py`), never
   `case.em_state` or `case.current_status.em` inline (AC-1). It raises
   `BtNodePreconditionError` when the case cannot be read (BT-HELPER-01): catch
   it in `update()` and return `FAILURE`, except in a refusal arm of a Selector,
   which lets it propagate (`notes/bt-pitfalls.md` § "A Refusal Arm in a
   Selector Fails Toward 'Admit'").

---

## Open Proposals Resolve Earliest-Expiration First (EP-08)

`EM.PROPOSED` means one or more proposals under negotiation; a counter-proposal
goes through the ordinary propose path (EMB-15-003), so several open entries are
routine. A participant SHOULD accept the **earliest-expiring** and handle the
rest as revisions (`docs/topics/process_models/em/defaults.md`).

- **Never select by insertion or arrival order.** Compare `end_time` with the
  shared comparator `earliest_ending` (`vultron/core/services/embargo_ordering.py`);
  a first-recorded selection once accepted superseded terms (#3470).
- **Decide through the register, on every decision path.** Owner accept
  (`ACTIVATE`), owner reject (`REJECT`), termination (`TERMINATE` plus `CANCEL`)
  and P/X/A abandonment (`CANCEL`) each change the entry through
  `EmbargoLifecycle`, which prunes the relay index in the same step. A decided
  proposal left selectable is a wrong answer, not a weaker guarantee. A
  participant's accept or reject is consent and changes no entry. Termination
  decides *every* open proposal (EP-08-004): with one active embargo
  (VP-04-002), each is a revision of it, and the register refuses `TERMINATED`
  beside `PROPOSED`.
- **A Reject names the active embargo or an open proposal — nothing else.**
  `record_embargo_rejection` treats the active one as consent withdrawal and an
  open one as refusal of its terms; anything else raises
  `VultronValidationError` (ADR-0093). Test seeding that hands the service an
  unknown embargo is a test bug.

There is no multi-candidate poll (ADR-0100): offer alternatives as several
`Invite`s. Re-proposing the remainder as revisions is deliberately manual
(`propose_embargo_revision_trigger_bt`).

---

## Embargo Negotiation Relays Through the CASE_MANAGER (EP-09, ADR-0113)

The EMB behavioural specs speak of peer Participants "receiving EP"; in this
topology a participant addresses its proposal to the CASE_MANAGER alone
(PCR-08-001), so **the Participant receiving EP or EV is the CASE_MANAGER**, and
every other participant learns the result from the ledger.

1. A participant sends its `Invite(EmbargoEvent)` to the CASE_MANAGER only. The
   published-default path emits no proposal, so nothing is relayed for it.
2. The CASE_MANAGER adjudicates: still eligible → `propose_embargo` under the
   role gate and the proposal is committed; P/X/A set → ER (EMB-01-002). The
   fan-out tells replicas only that the case is under proposal or revision
   (EP-09-001).
3. The CASE_MANAGER relays an Invite to **every participant except the
   proposer** (`actor=CASE_MANAGER`, `attributed_to=proposer`, CM-24), each with
   its own RSVP `end_time` (CM-28-012), commits each emission, and applies PEC
   `INVITE` where legal (EP-09-002, CM-28-013). The proposer is not invited
   (proposing is consenting, ADR-0093). The same commit writes the rows no Invite
   will: the proposer's `AGREED`, and a stakeholder manager's own row by policy
   call-out (EP-09-005, `nodes/manager_consent.py`), in the manager's store only.
4. A participant answers the Invite addressed to it through the response
   decision tree and writes **no** case, consent or deadline state on receipt;
   consent moves when the CASE_MANAGER commits the answer (EP-09-003). Anything
   but the sole `to` recipient is refused as misrouting (EP-09-010). A revision
   Invite lands on the revision's own row; the signatory keeps its `AGREED` row
   (EP-09-004).
5. The owner's answer is consent *and* decision. The owner MAY decide without
   waiting (EP-09-005) and SHOULD gauge some answers (EP-09-006); any quorum is
   actor policy, a call-out point. The Invites are not a vote: they gather the
   consent rows that decide who stays bound when terms lengthen (EP-05-001).
6. Only the CASE_MANAGER evaluates expiry (CM-28-014). Replay nodes reconstruct
   proposal, relayed Invites, answers and decision via
   `EmbargoLifecycle(OBSERVED)` (EP-09-007, RSH-08-004); the slot table is in
   `notes/case-communication-model.md` § "What the participant and its replica
   do".

**The ledger never asks.** An announced proposal or Invite sets no
parse-and-respond expectation; a participant answers only an Invite addressed
to it. A handler for "a non-manager received a peer's proposal" is a handler for
a misrouting (RSH-08-003: store it, write nothing).

**The commit is the acknowledgement.** "Emit EK" is discharged by the
CASE_MANAGER's commit and announcement; no EK message exists or is to be built
(EP-09-009, MSM-02-009).

**A trigger writes shared EM state only as the CASE_MANAGER (EP-09-008).** Each
tree in `vultron/core/behaviors/embargo/trigger_tree.py` ends in two exclusive
arms built by `_by_role()` (BT-17-001). Ratchet:
`test/architecture/test_embargo_trigger_writes_are_case_manager_gated.py`.

- **As the CASE_MANAGER**: the `*EmbargoLifecycleNode` write runs `STRICT`, then
  `CommitEmbargoDecisionNode` commits the decision's sealed blob and only then
  queues it. Nothing is addressed to the manager itself (CLP-10-001): an
  `Accept`/`Reject` is only committed, its own proposal is relayed as one Invite
  per other participant, its teardown goes to every other participant
  (EMB-19-001). `EmitCaseStatusUpdateNode` follows, because RSH-04-002 requires a
  `CaseStatus` write after every EM mutation on a trigger path.
- **As anyone else**: the tree writes and declares no EM state; it queues the
  activity to the CASE_MANAGER and `SvcEmbargoTriggerBase` records it with
  `record_pending_assertion()` (SYNC-11-002), keyed by `subject_id`, so a repeat
  inside the window is suppressed. The announced commit clears it (SYNC-11-003);
  a refused proposal is closed by the manager's `Reject`
  (`close_refused_embargo_proposal`).

The receive-side cascade (`ThreatTerminationBranchNode`) reaches the same
`terminate_embargo_bt`, so a non-manager receiver asks too, and that ask is a
pending assertion: `TeardownAskPendingNode` suppresses a repeat, and trigger and
cascade suppress each other (#4147).

**A replica never asks for a teardown the CASE_MANAGER declared** (RSH-03-004).
The declaration can arrive before the teardown entries, so
`_DeclaredByCaseManagerNode` skips the branch when the status's sender holds
CASE_MANAGER and is not the executing actor. It decides *who* tears down, not
*whether* — it is not a sender-role authorization gate (RSH-03-002). For the
same reason `PxaEmInvariantDiagnosticNode` posts no CSB-18 Note for such a
status.

**The P/X/A abandonment decides every open proposal (EMB-16-001).** The
CASE_MANAGER commits one `Reject(Invite(EmbargoEvent))` per proposal under
`reject_invite_to_embargo_on_case_abandoned`, addressed to nobody, and cancels
each proposal (`abandon_embargo_proposals`, STRICT) only after its entry commits,
so a failed commit leaves that proposal open (CLP-07-013, #4442). Replicas drop
them through the `EmbargoAbandonment` slot without repeating the owner check.

**A non-manager sends no ER for the abandonment (EMB-16-002).** Its ER would read
at the manager as declining the proposal (MSM-07-004), an abandonment it has no
standing to make; its P/X/A status already reaches the manager, which abandons
on that. `LeaveAbandonmentToCaseManagerNode` writes and sends nothing. This is
distinct from EMB-01-002: a proposal *addressed to* a participant that believes
P/X/A is set is still answered with ER, manager or not. Participant self-status
(RM) keeps its local write.

**The role is never unfilled** (CM-24-006). No "no manager" arm belongs in any
embargo tree; a resolver that finds nobody fails.

**Only the CASE_MANAGER records an answer, and only one it can apply.** Answer
and owner-decision effects sit behind the CASE_MANAGER gate; anyone else reports
`REFUSED` and writes nothing (HP-01-005). Refuse before the guarded commit, with
read-only guards (`IsRejectableEmbargoNode`, `IsOpenEmbargoProposalNode`,
`OwnerMayActivateEmbargoNode`): once committed, a failing replica apply blocks
its persist (SYNC-12-001) and stalls every later entry (SYNC-14-001).

**The owner's `Reject(EmbargoEvent)` decides one proposal**; EM stays
`PROPOSED`/`REVISE` while another is open (EP-08-003). Rejecting the last open
revision after P/X/A runs the terminate path (ET) instead of restoring the prior
terms (EMB-04-002).

**RSH-04-002 on the relay trees.** These received trees add no
`EmitCaseStatusUpdateNode`: the guarded commit records the causing activity and
its relay apply node replays the transition everywhere, so a second `CaseStatus`
entry would duplicate it.

The creation-time revision follows the same relay (EP-04-011) — see
`notes/embargo-default-semantics.md`.

## Who May Send Each Embargo Message (ADR-0115, HP-01-006)

A received embargo activity asserts its sender's standing, so each handler
checks the sender before it writes, sends or commits anything. The rule depends
on the receiver (PCR-03-001, PCR-08-001):

| Message | At the CASE_MANAGER | At any other replica |
|---|---|---|
| `Invite(EmbargoEvent)` | an active participant (CM-10-004) | the CASE_MANAGER (EP-09-003) |
| `Accept` / `Reject(Invite)` | the recorded Invite's sole `to` recipient (EP-09-010) | the same; the answer is then refused by the role gate |
| `Create` / `Add` / `Remove(EmbargoEvent)` | the Case Owner, or the CASE_MANAGER itself | the CASE_MANAGER |
| `Announce(EmbargoEvent)` | the CASE_MANAGER | the CASE_MANAGER |

The shared nodes are `SenderMayAssertEmbargoNode` and `SenderIsInviteeNode`
(`vultron/core/behaviors/sender_entitlement.py`).

- **The invitee comes from the store, never from the reply**, so a reply
  embedding a doctored Invite cannot name itself the invitee; an Invite the store
  never recorded names no invitee and is refused.
- **A handler that writes before its tree runs checks first** through
  `sender_refusal()`; the tree carries the guard as well, in the factory's sender
  stage.

The `Create`/`Add`/`Remove` row at the CASE_MANAGER is not stated by a spec; it
follows EP-09-005 (the owner decides) and the ER-never-ET rule above.
