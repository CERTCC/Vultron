---
title: Embargo Lifecycle — Architecture and Implementation Notes
status: active
kind: guidance
description: >
  Rules for changing embargo state: the embargo register from which EM is
  derived, changed one checked step at a time along an EM transition, by
  EmbargoLifecycle or, for an arm converted to the copy model, the one apply
  function (ADR-0122, ADR-0124, ADR-0130); consent versus owner decision; STRICT
  versus OBSERVED and the P/X/A guards; the invariant that a case never names
  an embargo its store cannot read (EMB-18-003); late Accepts, expiry, the
  overdue-invitation sweep and the owner-close settle step (EMB-17, CM-28-015,
  CM-23-014); P/X/A refusal and teardown
  (EMB-01-002, EMB-16); earliest-expiration resolution of open proposals
  (EP-08); the relay through the CASE_MANAGER and its trigger write gate
  (EP-09, ADR-0113); who may send each embargo message (ADR-0115); and which
  bound holds the manager's own work — the tree's path declaration or the
  CASE_MANAGER gate (HP-01-038, ADR-0153).
related_specs:
  - specs/case-management.yaml
  - specs/datalayer.yaml
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
  - specs/actor-knowledge-model.yaml
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
  - vultron/core/models/embargo_register/
  - vultron/core/models/embargo_termination.py
  - vultron/core/services/embargo_lifecycle/
  - vultron/core/services/carried_embargo.py
  - vultron/core/services/embargo_availability.py
  - vultron/core/behaviors/embargo/
  - vultron/core/models/pending_assertion/
  - vultron/core/use_cases/triggers/embargo/
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
  not in the table (`em_move_violations()`, EMB-18-013/014); the check is in the
  step, so the CASE_MANAGER and every replica apply it alike. With several
  proposals open, `reject` and `accept` self-loop, and activating one proposal
  leaves the others open as revisions.
- **`CaseStatus.em` is a frozen stamped copy.** Core reads `case.em_state`,
  never the copy. `append_case_status(em=...)` is refused, and a received
  `Add(CaseStatus)` whose EM differs is refused whole (RSH-09-005,
  SDO-03-006).
- **A termination records what and why (ADR-0122, EMB-13-004, EMB-13-010).** The what
  (`TerminationReason`: `END_TIME_REACHED` or `EARLY`) is the `Remove`'s
  `content`, parsed at the edge (`termination_reason_from_content()`); the why
  is a structured cause (`vultron/core/models/embargo_termination.py`), a
  union discriminated on `kind`: `THREAT_SIGNAL` (`P`/`X`/`A`), `FIX_READY`
  (the quorum's vendors), `FIX_DEPLOYED` and `OTHER` (ADR-0122 rev 7). Both
  sit on the `TERMINATED`
  entry as one `EmbargoTermination`, required there and refused elsewhere. The
  cascades pass `ThreatSignalTermination(signals=...)`: the signals of the
  triggering status, or, when unknown at build time, the case's PXA at the
  write. A voluntary termination passes `ChosenTermination`, set by the
  `ChooseTerminationCauseNode` after the reason call-out that succeeded and
  read at the write, so the choice and the commit are one act (EMB-14-001/006,
  EMB-14-004/007);
  the trigger records the request's cause, or `OTHER` when it names none.
  The `Remove` carries the why as `terminationCause` (a field on the
  base `as_Remove`, marked a Vultron property so `context.jsonld` names it),
  checked at the parse edge (EMB-13-005, EMB-13-012), because a replica learns the why
  only from the ledger entry: it copies the cause, never works it out from its
  own PXA (`ApplyEmbargoTeardownNode`). Every `Remove` the CASE_MANAGER sends
  passes the cause it records to `terminate_embargo(cause=...)`. An owner's
  `Remove` may claim `FIX_READY`, `FIX_DEPLOYED` or `OTHER`, recorded as
  given; one naming `THREAT_SIGNAL` is refused before the commit
  (`TerminationCauseIsAdmissibleNode`), since a threat signal arrives as a
  case status update setting `P`, `X` or `A`.
  The CASE_MANAGER decides the termination first (`decide_termination()`),
  builds its `Remove` from that decision, commits it, and only then applies
  the step (#4714), so the wire and the entry cannot disagree. The CM-31-009
  notices read the what back from the register (`case.embargo_termination`).
  A `Remove` naming an embargo not in force changes nothing, on the
  CASE_MANAGER and on a replica. Exception: a paused signatory's replica that
  has not activated the named revision activates it, then ends it (CM-31-042).
- **End-time termination is one idempotent path (EMB-13-003).**
  `end_embargo_at_end_time_bt` (`behaviors/embargo/end_time_tree.py`) answers an
  already-`EXITED` case as done and otherwise runs `terminate_embargo_bt` with
  `END_TIME_REACHED`. The CASE_MANAGER's lazy check (`end_time_clock_decision`) is a
  clock decision in the one tree, never a dispatcher hook or a tree run before it: the
  received-tree factory adds it to every case tree with both door guards, so a sender
  with no standing never provokes the termination (CLP-10-025), and `SvcBTTriggerBase`
  runs it as the first, CASE_MANAGER-gated step of every case-scoped trigger's tree
  (BT-15-003). It commits one entry per AS2 activity — the `Remove`, whose register
  step cancels every open proposal, then the `Add(CaseStatus)` and re-issued stubs —
  so no prefix of them shows `TERMINATED` beside `PROPOSED` (EP-08-004). A Sentinel reaches
  the path through the terminate trigger with `reason=END_TIME_REACHED`. That trigger
  sets `_takes_case_clock_decisions = False`: it takes the end-time path itself once
  the end time has passed, an `EARLY` request included, so the lazy check never
  pre-empts the answer it owes. `termination_timing_violations()` refuses an
  `END_TIME_REACHED` claimed before the end time — in the trigger's `_prepare`, the
  lifecycle, the received tree's guard
  (`TerminationIsTimelyNode`, before the commit) and replica replay.

---

## Consent and Decision Are Separate Operations

An answer to an Invite and the owner's decision on a proposal are separate
messages, so they are separate `EmbargoLifecycle` operations (ADR-0122):

- `accept_embargo_invite` / `record_embargo_rejection` record a sender's own
  consent to `Accept`/`Reject(Invite(EmbargoEvent))` — the owner's included —
  and move no register entry (MSM-07-011, MSM-07-013).
- `activate_embargo` / `reject_embargo_proposal` apply the owner's
  `Add`/`Reject(EmbargoEvent)[target=VulnerabilityCase]` (MSM-07-008, MSM-07-009).
- No operation branches on whether the sender is the owner. The accept and
  reject triggers pick by actor: an owner sends its decision, anyone else its
  consent. The one exception is an owner whose row reads `DECLINED`:
  `accept-embargo` sends its `Accept(Invite(EmbargoEvent))`, since its `Add`
  would be refused (MSM-07-037).
- An owner whose row is `DECLINED` cannot activate: the CASE_MANAGER refuses
  it before the commit, and the notice tells the owner to accept the Invite
  first, so one activity never both decides the case and changes the owner's
  answer (MSM-07-037, ADR-0180). From `UNINVITED`, `INVITED` or `TIMED_OUT`
  the activation agrees for the owner (MSM-07-028). The received
  owner-decision trees check P/X/A and the decline with a read-only guard
  ahead of the commit (`OwnerMayActivateEmbargoNode`), because a replica
  copies the step and does not re-check.
- A repeat of a recorded Accept or Reject is `SKIPPED` before the commit
  (`EmbargoAnswerNotRecordedNode`, CM-13-005); a `DECLINED` actor's Reject of
  an unknown embargo stays `REFUSED` (HP-01-003). An Accept after a Reject is
  a change of answer and moves the row straight to `AGREED` (CM-18-003).
- A proposal of terms the case already holds is `SKIPPED` before the commit
  (`EmbargoTermsNotHeldNode`, EP-09-032): its end time equals a pending
  proposal's, or, with no revision pending, the embargo in force's. Keep the
  in-force end time during a revision admissible, because it is the
  counter-proposal to keep the current terms (EP-09-020). The CASE_MANAGER's
  own propose and revise triggers compose the same node, given `result_out`, so
  there the repeat refuses the whole request instead: a trigger admits only
  valid steps (RSH-09, #5899).

## TransitionMode and the P/X/A Guards

- **`STRICT`** raises on a refused step and enforces the P/X/A guards. Only a
  trigger's CASE_MANAGER arm runs it (EP-09-014).
- **`OBSERVED`** follows the CASE_MANAGER's committed assertion. Only the
  paused replica's CM-31-010 notice path still runs it
  (`ending_notice_replica.py`, outside the ledger): it skips the P/X/A
  guards, records a proposal a replica never saw before activating it, and
  logs and skips a refused step — it never forces the register into a state
  its rules refuse. A copying replay node runs no lifecycle mode at all: it
  writes what the entry carries through `apply_embargo_change()` (ADR-0124).
- **P/X/A guards** (EMB-01-002, EMB-02-002, EMB-04-002): `propose_embargo()` and
  `activate_embargo()` raise when any of P/X/A is set; consent recording is
  never blocked. `reject_embargo_proposal()` does not refuse a rejection that
  returns a `REVISE` case to the prior terms with P/X/A set: the CASE_MANAGER
  records the `REJECT` step and then terminates the embargo in the same act
  (`end_embargo_outliving_disclosure_bt` around `terminate_embargo_bt`), so
  the revision ends `REJECTED` and the embargo `TERMINATED` with the threat
  signals as the cause its `Remove` carries (MSM-07-032, EMB-13-005).
  `OwnerRejectionAppliesNode` trial-applies both steps among the guards, and
  the act is one transaction, so a refused termination commits neither entry.
  Only the CASE_MANAGER reads `rejection_ends_embargo`
  (`vultron/core/predicates/embargo.py`); replicas copy both entries and
  decide nothing (CM-23-044).

## A Case Never Points at an Embargo Its Store Cannot Read (EMB-18-003)

The EP-05-001 comparison reads the revised and the replaced embargo, so every
path that writes `active_embargo` must hold the record first. The writers fail
closed on an unreadable record. A replica lacking the replaced embargo of an
announced revision fetches it from the CASE_MANAGER before dispatch and refuses
only when the fetch fails (EMB-18-007, AKM-05-015); the CASE_MANAGER has nobody
to fetch from, so there it is a broken invariant and refused. Build no other
catch-up path.

- **Seeding.** A sender carries `active_embargo` inline in every outbound case
  and refuses to build the activity if its own store cannot read it. Every
  receiving writer calls `store_carried_embargo()`
  (`vultron/core/services/carried_embargo.py`) before saving the case; a case
  naming an unreadable embargo is refused and nothing is saved. An inline
  embargo whose `context` is neither the carrying case nor one of its reports
  is refused unstored, because a first write wins and a sender must not plant
  another case's embargo. The record already held under the id is checked too,
  inline or bare id, since the case names the held record (EMB-18-004,
  `hold_embargo_for_case()`). A report counts because the Reporter holds its
  own proposal about the report it submitted (EP-04-009).
- **Ledger replay.** Each embargo apply node stores the `EmbargoEvent` its entry
  carries before calling `EmbargoLifecycle`, and fails (blocking the persist,
  SYNC-12-004) when the entry names it by id only and the replica lacks it.
  The entry's inline copy and the record already held under its id must each
  be about the case or a report of the replica's stored case, or the entry is
  refused (EMB-18-004, `carried_entry_embargo()`, `entry_embargo()`).
- **Activation.** `activate_embargo()` and `initialize_creation_embargo()` read
  the activated record, and on a revision the replaced one, through
  `_activation_arm()` before any write, raising in either mode. The owner's
  activation then reports `REFUSED` (HP-01-003). Recording consent reads no
  embargo record and has no such failure.

## Late Accepts and Expiry (EMB-17, CM-23-014)

- **An `Accept(Invite(EmbargoEvent))` is answered by whether the embargo it
  names is available, on time or late** (MSM-07-012, EMB-17-001): the Active
  Embargo or an open proposal, before its end time. A late one first commits the
  CASE_MANAGER's `Update(EmbargoConsent)` carrying the `TIMED_OUT` row if the row
  still needs `TIME_OUT` (the Accept tree's clock decision, CLP-10-025); after
  that the deadline decides nothing. An available embargo is honoured: the Accept
  is committed as an on-time one is (EMB-17-002, ADR-0152). One the register
  holds but that is not available is refused uncommitted with the refusal
  notice, plus a re-invite to the case's terms when it holds any (EMB-17-003).
  One the register never held gets `Create(ProcessingFault)` and no notice
  (MSM-07-039). **Read availability through `embargo_availability`
  (`vultron/core/services/embargo_availability.py`), never `active_embargo_id`
  alone and never the register status alone**: a case under proposal has no
  embargo in force, and an `ACTIVE` entry past its `end_time` binds nobody
  before the clock terminates it. `available_terms` reads the re-invite's terms
  by the same test, so the refusal and the re-invite cannot disagree, and the
  re-invite asks only a row `INVITE` moves (an `INVITED` or `AGREED` row is
  already asked or answered, CM-18-003; `ReinviteRefusedAccepterNode`). The
  notice and the re-invite are one act in the `UnavailableEmbargoRefusal`
  diversion (`vultron/core/behaviors/embargo/accept_availability_tree.py`), so a
  failed re-invite sends no notice either (CLP-07-016). Each runs only at the
  CASE_MANAGER: the Accept tree declares that path alone, and a non-manager gets
  `REFUSED` and changes no consent (BT-17-001, HP-01-038). The outcome table is in
  `notes/participant-embargo-consent.md` § "Expiry is lazy, and only the
  CASE_MANAGER's".
- **Owner close settles pending Invites without waiting.** After close an Invite
  can only expire, so `ExpirePendingInvitesOnCloseNode` runs right after the
  `close_case` entry, before any closure step: the CASE_MANAGER's own
  `RM.CLOSED` entry is the write boundary, and a Case Owner holding
  CASE_MANAGER writes it in its own closure. It reuses the
  late-Accept expiry subtree for each pending invitation. Its `published` is the
  CASE_MANAGER's clock, because the invitee sent nothing. Each expiry commits
  before it writes the consent row, so a refused one writes nothing; it is
  logged and the close goes on.
- **Every embargo act sweeps overdue Invites first (CM-28-015).** Each received
  embargo tree and embargo trigger takes `ExpireOverdueInvitesNode` as a clock
  decision, after the end-time check: it expires every `INVITED` row past its
  deadline on an open proposal or the embargo in force. It shares
  `ExpireInvitationsNode` with the settle step, so the expiry path is one copy,
  and it runs before the activity's own guards, so a refused activity still
  leaves its expiries recorded (ADR-0135). See
  `notes/participant-embargo-consent.md` § "Sweep due expiries before the owner
  decides".

## Refusing an Invite at P/X/A (EMB-01-002)

- The P/X/A refusal of a received Invite or Accept is a `RECEIVER`
  diversion of the received tree (`pxa_invite_refusal`, `pxa_accept_refusal`
  in `vultron/core/behaviors/embargo/refusal_tree.py`, CLP-10-026), never a
  refusal effect: refusal effects run only at the CASE_MANAGER and are skipped
  on a redelivery, and a participant owes the `Reject` too and re-queues one
  sealed but never queued (EMB-01-007, ID-04-005). The `Reject` is the
  receiver's own answer, not ER (MSM-02-010). It stores the Invite's
  `EmbargoEvent` first; the refusal factory reads the proposal from intake's
  archive, never a copy under the sender's id (DL-06-006). It answers where
  any Invite answer goes: the CASE_MANAGER answers the proposer, a participant
  answers the CASE_MANAGER, never a peer (PCR-08-001). An Invite naming its
  terms by URI only is answered once its terms are fetched, and not when the
  fetch fails (EMB-01-002, AKM-05-015).
- **Skip an Invite already answered** (`pending_embargo_proposal_index` maps its
  embargo to it), so a later P/X/A never contradicts an earlier answer.
  "Already recorded" is not that signal: intake records the Invite once its
  doors admit it, before any guard runs (CLP-10-017).
- **The refusal `Reject` is its own record** (ADR-0123). Its id derives from the
  rejecting actor and the Invite, a tree node queues it (CLP-10-020), and the
  sealed `Reject` is written before the queue append (EMB-01-006), so a
  redelivery is `SKIPPED`.
- An Invite naming no `to` recipient, several, or no embargo is answered with
  `Create(ProcessingFault)`, not a `Reject` (EP-09-026, MSM-05-001), by the one tree
  `received_embargo_invite_tree` builds for it (`invite_received_tree.py`),
  after the post-close boundary.

**A participant answers a revision on a P/X/A case with its own `Reject` of the
Invite, never ET** (EMB-03-003, EMB-03-004, ADR-0118). Termination belongs to
the owner, or to the CASE_MANAGER when delegated (EP-09-008); a participant's ET
would write shared EM state it does not own. The duty binds only the addressee: the
`ActivityAddressedToReceiverNode` door guard that `create_receive_activity_tree`
places in every received tree refuses an unaddressed copy before anything
answers it (HP-01-005, CLP-10-010).

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

1. **Decide through `EmbargoLifecycle`, write by copying**
   (`vultron/core/services/embargo_lifecycle/`, `embargo_apply/`). A
   committed step is written through `apply_embargo_change()`; BT nodes MUST
   NOT otherwise apply a register step, assign `case.current_status.em`, and
   `dl.save(case)` themselves (EMB-18-001, EMB-18-008). A refused step raises or
   fails the node without a write (EMB-18-009). Lifecycle nodes catch `VultronError` and
   return `FAILURE`; triggers are thin orchestrators over the service.
2. **On `VultronInvalidStateTransitionError` from a P/X/A guard**, the case is no
   longer embargo-eligible: do not retry; answer the proposer with a `Reject` of
   the Invite.
3. **Consent cascades are automatic.** `propose_embargo()` changes no consent
   except recording the proposer's (ADR-0093). An activation records the
   owner's agreement; a *shorter* replacement carries every signatory over
   (`CARRY_OVER`), and under *longer* terms non-agreeing signatories lapse by
   derivation (MSM-07-020). The CASE_MANAGER decides these
   (`decide_activation()`) and commits each carried-over row as its own
   `Update(EmbargoConsent)` entry after the `Accept`; replicas copy them and
   run no carry-over (ADR-0124, #4716). Termination (`decide_termination()`,
   then the `TERMINATE` step through the one apply function) cancels every
   open proposal and writes no consent (MSM-07-025). Callers do none of this
   by hand.
4. **Replay copies.** The proposal, relay, answer, re-invite, abandonment,
   teardown, withdrawal, activation, owner's-rejection and expiry slots copy
   the entry's step or row (a `Leave` carries none), and every other row
   arrives as its own CASE_MANAGER entry (ADR-0124). No slot decides to skip
   an entry (CM-23-044, MSM-07-009; see the P/X/A guards above). One path
   still passes
   `transition_mode=TransitionMode.OBSERVED`: a paused replica applying a
   CM-31-010 notice, which is outside the ledger (`ending_notice_replica.py`).
   Two checks hold this: `test/architecture/test_embargo_replica_slots_copy.py`
   keeps every replica embargo slot, and every helper it reaches, free of
   lifecycle calls, and every per-actor-store scenario and exchange demo is
   rebuilt from the CASE_MANAGER's ledger into an empty store and compared
   (`test/support/ledger_rebuild.py`). A test that writes the CASE_MANAGER's
   store outside the ledger on purpose calls `LedgerNetwork.bypass_ledger()`.
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
goes through the ordinary propose path (EMB-15-011), so several open entries are
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
  `record_embargo_rejection` declines the named row; anything else raises
  `VultronValidationError` (ADR-0093). A Reject of the active embargo from an
  `AGREED` row raises too: withdrawal is `record_embargo_withdrawal`, the
  effect of `Leave(EmbargoEvent)` (MSM-07-010). Test seeding that hands the
  service an unknown embargo is a test bug.

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
   role gate and the proposal is committed; P/X/A set → its `Reject` of the
   Invite (EMB-01-002). The
   fan-out tells replicas only that the case is under proposal or revision
   (EP-09-001).
3. The CASE_MANAGER relays an Invite to **every participant except the
   proposer** (`actor=CASE_MANAGER`, `attributed_to=proposer`, CM-24), each with
   its own RSVP `end_time` (CM-28-012), commits each emission, and applies PEC
   `INVITE` where legal (EP-09-002, EP-09-022, CM-28-013). The proposer is not
   invited (proposing is consenting, ADR-0093). The same commit writes the rows no
   Invite will: the proposer's `AGREED` (EP-09-023), and a stakeholder manager's
   own row by policy call-out (EP-09-024, EP-09-005, `nodes/manager_consent.py`),
   in the manager's store only.
4. A participant answers the Invite addressed to it through the response
   decision tree and writes **no** case, consent or deadline state on receipt;
   consent moves when the CASE_MANAGER commits the answer (EP-09-003). Anything
   but the sole `to` recipient is refused as misrouting (EP-09-026). A revision
   Invite lands on the revision's own row; the signatory keeps its `AGREED` row
   (EP-09-004).
5. The owner's answer is consent *and* decision. The owner MAY decide without
   waiting (EP-09-005) and SHOULD gauge some answers (EP-09-006); any quorum is
   actor policy, a call-out point. The Invites are not a vote: they gather the
   consent rows that decide who stays bound when terms lengthen (EP-05-001).
6. Only the CASE_MANAGER evaluates expiry (CM-28-014). Replay nodes copy the
   proposal's `PROPOSE` step, the owner's `ACTIVATE` or `REJECT`, and every
   consent row the CASE_MANAGER commits as its own entry (EP-09-007,
   RSH-08-004, ADR-0124); the slot table is in
   `notes/case-communication-model.md` § "What the participant and its replica
   do".

**The ledger never asks.** An announced proposal or Invite sets no
parse-and-respond expectation; a participant answers only an Invite addressed
to it. A handler for "a non-manager received a peer's proposal" is a handler for
a misrouting (RSH-08-003: store it, write nothing).

**The commit is the acknowledgement.** "Emit EK" is discharged by the
CASE_MANAGER's commit and announcement; no EK message exists or is to be built
(EP-09-009, MSM-02-009).

**A trigger writes shared EM state only as the CASE_MANAGER (EP-09-008,
EP-09-014).** Each
tree in `vultron/core/behaviors/embargo/trigger_tree/` ends in two exclusive
arms built by `_by_role()` (`trigger_tree/_arms.py`, BT-17-001). Ratchet:
`test/architecture/test_embargo_trigger_writes_are_case_manager_gated.py`.

- **As the CASE_MANAGER**: the `*EmbargoLifecycleNode` write runs `STRICT`, then
  `CommitEmbargoDecisionNode` commits the decision's sealed blob and only then
  queues it. Nothing is addressed to the manager itself (CLP-10-032): an
  `Accept`/`Reject` is only committed, its own proposal is relayed as one Invite
  per other participant, its teardown goes to every other participant
  (EMB-19-003). `EmitCaseStatusUpdateNode` follows, because RSH-04-002 requires a
  `CaseStatus` write after every EM mutation on a trigger path.
- **As anyone else**: the tree writes and declares no EM state; it queues the
  activity to the CASE_MANAGER and `SvcEmbargoTriggerBase` records it with
  `record_pending_assertion()` (SYNC-11-002), keyed by `subject_id`, so a repeat
  inside the window is suppressed. The announced commit clears it (SYNC-11-003);
  a refused proposal, or an `Accept` refused with a `Reject` of the Invite
  (EMB-02-004), is closed by the manager's `Reject` (EP-09-019,
  `close_refused_embargo_ask`); a duplicate proposal (EP-09-032) is neither
  committed nor refused, so its entry closes only on the timeout
  (SYNC-11-005); a participant takes a
  `Reject(Invite(EmbargoEvent))` from the CASE_MANAGER alone.

The receive-side cascade (`ThreatTerminationBranchNode`) reaches the same
`terminate_embargo_bt`. Run as a non-manager it would ask too, as a pending
assertion: `TeardownAskPendingNode` suppresses a repeat, and trigger and cascade
suppress each other (#4147). No received tree runs it off the CASE_MANAGER
(next rule).

**A replica never asks for a teardown the CASE_MANAGER declared** (RSH-03-004).
The CASE_MANAGER only ledgers its own status, and the threat teardown runs only
in `add_participant_status_tree` under the CASE_MANAGER gate, so a replica learns
the teardown from the committed entries alone. It decides *who* tears down, not
*whether* (RSH-03-002). The CSB-18 diagnostic runs only at the CASE_MANAGER too
(#4829).

**The P/X/A abandonment decides every open proposal (EMB-16-001).** After
`check_abandonable` passes, the CASE_MANAGER commits, per proposal, the
activity that cancels it, then an `Undo(Invite(EmbargoEvent))` of each Invite
it relayed for it, all addressed to nobody and all in one transaction
(CLP-07-015). The cancel follows the Invite's shape (ADR-0152): a
`Reject(Invite(EmbargoEvent))` of a proposal it received, committed as
`reject_invite_to_embargo_on_case`, or an `Undo` of a proposal it sent itself,
as `undo_invite_to_embargo_on_case`. It cancels each proposal by copying the
`CANCEL` step only after its entry commits (CLP-07-013, ADR-0124). A replica
tells the manager's `Reject` from a participant's by the payload's `actor`
(`sent_by_case_manager`), copies the `CANCEL` from it, and finds each later
`Undo` already in place.

**A non-manager sends no ER for the abandonment (EMB-16-002).** Its `Reject` of
the Invite would read at the manager as declining the proposal (MSM-07-004), an
abandonment it has no standing to make; its P/X/A status already reaches the
manager, which abandons on that. `LeaveAbandonmentToCaseManagerNode` writes and
sends nothing. This is distinct from EMB-01-002: a proposal *addressed to* a
participant that believes P/X/A is set is still answered with its own `Reject`
of the Invite, manager or not. Participant self-status (RM) keeps its local
write.

**The role is never unfilled** (CM-02-014, CM-24-008, CM-24-015). No "no manager" arm belongs
in any embargo tree; a resolver that finds nobody fails.

**Only the CASE_MANAGER records an answer, and only one it can apply.** Answer
and owner-decision effects are bounded two ways, and which one applies is the
tree's path declaration (HP-01-038): a tree that declares the CASE_MANAGER path
alone is bounded by the path stage, which refuses every other receiver before
any guard runs, so its guards and diversion need no gate; a tree that declares
another path beside it keeps the CASE_MANAGER gate, or an
`OnPaths.at_case_manager(...)` branch, around the manager's own work. Either
way anyone else reports `REFUSED` and writes nothing (HP-01-005). Refuse before
the guarded commit, with
read-only guards or diversions (`IsAnswerableEmbargoNode` for a `Reject`, the
availability diversions for an `Accept`, `IsOpenEmbargoProposalNode`,
`OwnerMayActivateEmbargoNode`): once committed, a failing replica apply blocks
its persist (SYNC-12-004) and stalls every later entry (SYNC-14-001).

**The owner's `Reject(EmbargoEvent)` decides one proposal**; EM stays
`PROPOSED`/`REVISE` while another is open (EP-08-003). Rejecting the last open
revision after P/X/A rejects it and then, in the same act, runs the terminate
path (ET), so the prior terms do not stand when the act ends (EMB-04-002,
MSM-07-032).

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
| `Invite(EmbargoEvent)` | an active participant (CM-10-004), or the CASE_MANAGER itself | the CASE_MANAGER (EP-09-003) |
| `Accept` / `Reject(Invite)` | the recorded Invite's sole `to` recipient (EP-09-010) | the same, but this rule is reached only when the tree declares the path. The Accept tree declares the CASE_MANAGER path alone, so the path stage refuses a replica before the sender guard runs; the Reject tree declares both paths, so a replica is admitted and the handler closes the participant's pending ask (HP-01-038, EP-09-017, EP-09-019) |
| `Remove(EmbargoEvent)` | the Case Owner, or the CASE_MANAGER itself | the CASE_MANAGER |
| `Announce(EmbargoEvent)` | the CASE_MANAGER | the CASE_MANAGER |

Each row is the use case's declared `SenderRule`, and the receive-tree factory
composes the guard from it (HP-01-025, `vultron/core/behaviors/sender_guard/`).
The embargo rows are checked in `embargo_sender_context()`: a store that holds no
case, or a case that names no CASE_MANAGER, refuses the sender rather than
passing it through. A proposer must be active (`ACTIVE_PARTICIPANT`), not only
listed (`PARTICIPANT`). The invitee rows use `SenderIsInviteeNode`.

- **The invitee comes from the store, never from the reply**, so a reply
  embedding a doctored Invite cannot name itself the invitee; an Invite the store
  never recorded names no invitee and is refused.
- **The sender guard is the tree's, in the factory's sender stage**, composed
  from the declared rule, the invitee rows included; no embargo handler checks
  the sender ahead of its tree, and none builds a sender node of its own
  (HP-01-007, CLP-10-005).

The `Remove` row at the CASE_MANAGER is not stated by a spec; it
follows EP-09-005 (the owner decides) and the reject-never-ET rule for a
P/X/A revision above.
