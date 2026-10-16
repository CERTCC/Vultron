---
title: Joining a Case — Stub Invite, Inert Participant, Full-Case Invite
status: active
kind: guidance
description: >
  Rules for how an actor goes from invited to participating: the stub-Invite
  flow, the one "active participant" predicate, authority to act, edge cases
  (expiry, refusals, re-invite, supersede), and removal and reinstatement, which
  withdraw and restore entitlement without touching membership (ADR-0116).
related_specs:
  - specs/case-management.yaml
  - specs/participant-role-management.yaml
  - specs/rm-behavior.yaml
  - specs/vultron-as2-mapping.yaml
  - specs/participant-case-replica.yaml
  - specs/sync-ledger-replication.yaml
  - specs/received-status-handling.yaml
  - specs/case-ledger-processing.yaml
  - specs/embargo-policy.yaml
  - specs/handler-protocol.yaml
related_notes:
  - notes/case-communication-model.md
  - notes/case-ledger-authority.md
  - notes/embargo-lifecycle.md
  - notes/participant-embargo-consent.md
  - notes/participant-role-management.md
  - notes/sync-ledger-replication.md
  - notes/stub-objects.md
  - notes/wire-core-boundary.md
  - notes/received-status-authorization.md
  - notes/case-state-model.md
  - notes/participant-case-replica.md
  - notes/demo-ci-scenario-coverage.md
  - notes/activitystreams-semantics.md
  - notes/protocol-event-cascades.md
relevant_packages:
  - vultron/core/participants/recipients.py
  - vultron/core/participants/stub_reply.py
  - vultron/core/models/case.py
  - vultron/core/models/case_participant.py
  - vultron/core/models/actor_recommendation_record.py
  - vultron/core/behaviors/case/nodes/invite_participant.py
  - vultron/core/behaviors/case/nodes/on_behalf_guards.py
  - vultron/core/behaviors/case/case_participant_received_tree.py
  - vultron/core/behaviors/sync/nodes/participant_removal_effect.py
  - vultron/core/behaviors/case/nodes/participant_reinstatement.py
  - vultron/core/behaviors/embargo/nodes/reinvite.py
  - vultron/core/behaviors/sender_entitlement.py
  - vultron/core/states/rm.py
  - vultron/wire/as2/factories/case.py
---

# Joining a Case — Stub Invite, Inert Participant, Full-Case Invite

Decisions: ADR-0114 (joining, inert participants, the stub type), ADR-0121 (judging
the case), ADR-0116 (removal and reinstatement). The participant-facing flow is in
`docs/reference/vultron-spec/_participant-lifecycle.md`.

## The flow

| Step | Message | RM | VF (vendor) | Embargo consent | Inert? |
|---|---|---|---|---|---|
| 1 | CASE_MANAGER sends `Invite(Actor, VulnerabilityCaseStub)`; record created | `RECEIVED` | `v` | `INVITED` if an embargo is active | yes |
| — | optional on-behalf `v→V` by the Case Manager or Case Owner | — | `V` | — | yes |
| 2a | `Accept(Invite(stub))` — join, and consent to the active embargo | `RECEIVED` | `V` | `AGREED` if an embargo is active | **no** |
| 2b | `Reject(Invite(stub))` — hard no | `CLOSED` | `V` | `DECLINED` if an embargo is active | yes, permanently |
| 3 | CASE_MANAGER sends `Announce(VulnerabilityCase)` and replays the ledger | — | — | — | no |
| 4 | CASE_MANAGER sends `Invite(Actor, VulnerabilityCase)` with its ledger position | — | — | — | no |
| 5a | `Accept(Invite(case))` (RV) | `VALID` | — | — | no |
| 5b | `TentativeReject(Invite(case))` (RI) | `INVALID` | — | — | no |
| 5c | `Reject(Invite(case))` (RC) | `CLOSED` | — | — | stops receiving |
| 6 | `Join(VulnerabilityCase)` (RA) / `Ignore(VulnerabilityCase)` (RD) | `ACCEPTED` / `DEFERRED` | — | — | no |

A stub Invite has two replies, not three: accepting a stub is not a judgement of the
case, so there is no `TentativeReject` handler for it.

### One predicate decides "active"

A participant is **active** when it was seated by case initialization (Case Owner,
CASE_MANAGER, reporter — never sent a stub) or accepted the stub Invite, is not
removed, and — only while an embargo is active — is a signatory to it. Many
cases have no active embargo, so "inert until a signatory" is wrong.

- The one check is `VulnerabilityCase.is_active_participant()`, read from the
  replicated `CaseParticipant` record and the case's `active_embargo`, so a replica
  answers as the CASE_MANAGER does. It is computed, never stored (CM-31-002): a stored
  "joined" property would read as "active" at a send site.
- Every case-content send picks recipients through
  `vultron/core/participants/recipients.py` (`case_content_recipients()`,
  `invitation_recipients()`), never at the send site (CM-10-004, CM-10-005). A roster
  entry whose record cannot be read gets nothing (CM-10-007).

### RM `CLOSED` ends content delivery (CM-23-004)

A `CLOSED` participant's replication is assumed to have exited, so it is sent no case
content, except the entries that record its own closure (CM-23-001): it receives every
step up to the one that reaches `CLOSED` and waits for them rather than writing
`CLOSED` itself. Later entries, `case_fully_closed` included, reach only participants
not yet closed. The exception never widens entitlement, and the CM-31-009 embargo
notice is the only other message a closed participant gets. Verify "all participants
closed" in the CASE_MANAGER's store (`vultron/demo/helpers/closure.py`), and check
each departing actor's replica only for its own closure. Closed-skipping is not an
option: the one ledger fan-out (`FanOutLogEntryNode`) uses
`ledger_entry_recipients()`, which adds back only the closed participant the entry
is about (`entry_records_own_closure()`), and a replay answering a closed peer's
`Reject(CaseLedgerEntry)` stops at `closed_participant_ledger_cutoff()`.

## Authority to act

Acting on a case — suggest an actor, add a note, change the roster — requires an
*active* participant: no actor acts on content it may not see. An inert participant may
only reply to the Invites addressed to it. A `CLOSED` participant may act on nothing
further, except the two acts below, and is sent no Invites (CM-11-015). The
CASE_MANAGER is held to the predicate as a recipient; its authority to *commit* comes
from its role (CLP-09).

- **A sender at RM `CLOSED` is refused, not just unsent-to (CM-23-018).** The
  `ACTIVE_PARTICIPANT` standing is "active and closure not recorded", asked through
  one shared predicate, `may_act_on_case()` in `core/participants/recipients.py`, by
  every guard node for that kind. The bare active check is
  not enough: it leaves `CLOSED` out on purpose, because recipients need it.
  A closed participant would otherwise write to a case it can no longer see
  (CM-23-004), and CM-23-013 stops writes only at `case_fully_closed`.
- **Two acts stay open to a closed sender.** `Reject(CaseLedgerEntry)` gets a replay
  capped at its own closure entries (`closed_participant_ledger_cutoff()`). Its guard
  stays the bare active check (SYNC-03-005), so its use case declares the
  `LEDGER_PEER` kind, never `ACTIVE_PARTICIPANT`. A repeat of an act that would
  close it again (`Leave`, a `Reject` of its Invite) is `SKIPPED`, with no entry,
  whatever its activity id: `closed_sender_preflight()` asks `closure_recorded()`
  before the tree runs. Any other invitee reply from it is `REFUSED` there too,
  since its guard is `INVITEE`, not the shared predicate. A `Close(Report)` on a
  case is refused from every sender, closed or not (CM-23-019).
- **A closed Case Owner holds no `CASE_OWNER` standing.** The factory composes the
  closure check ahead of the role check for that kind (`_case_owner_node()`), and
  leaves `SenderIsCaseOwnerNode` asking the role alone, since the Leave, status,
  suggest-actor and embargo trees read it to pick an arm (CM-23-018).
- **A repeat is decided by its effect, not its id (ID-05-003).** An act whose effect
  is already in place is a no-op, even under a new activity id: you cannot leave
  twice.

## Edge cases

- **Unanswered stub Invite.** Its `Invite.end_time` is stamped as for a relayed embargo
  Invite (CM-28-012). Expiry is read (`now >= end_time`, on the CASE_MANAGER's copy),
  never recorded: the Invite closes as an expired ask, the record stays inert at
  `RECEIVED`, consent stays `INVITED`, and no entry is written (CM-11-014). The
  `TIMED_OUT` rule (CM-28-004) is for embargo Invites only. Expiry is *stale*
  (ASK-03-002): a late `Accept` still joins and a late `Reject` still closes.
  "All participants closed" counts only participants that joined.
- **Refusals (nothing written).** A stub Invite with no roles or no stub summary
  (CM-11-019, CM-17-010); an `Accept` or `Reject` of a stub from an invitee with no
  participant record (CM-11-018, CM-11-021) — never a silent no-op, never creates a
  participant; a full-case Invite reply from a participant that has not joined
  (CM-11-012).
- **No roles means refuse, never default to VENDOR (CM-11-019).**
  `EvaluateDefaultRolesNode` returns `[]`, which the trigger turns into REFUSED;
  `CreateInertInviteeParticipantNode` enforces the same rule.
- **Re-invite.** Same record, fresh stub Invite and deadline, `inReplyTo` the earlier
  stub. Refused for a `CLOSED` participant (no rejoin, ADR-0085) and for one already
  joined, before anything is queued or committed (`SuggestedActorIsInvitableNode`,
  CM-16-006). The re-invite arm sits ahead of the duplicate arms, because an inert
  record is on the roster and its stub is "in flight".
- **Embargo changes during the invitation window (CM-11-016).** The CASE_MANAGER
  re-issues an *outstanding* stub (unanswered, unexpired) with current terms, naming
  the one it supersedes. `Accept` of a superseded stub is refused with the replacement
  named; `Reject` of it is honoured. The check compares each stub's embargo with the
  one a new stub would carry, so it runs after any step that may change the embargo,
  and does nothing while a proposal is open. Retracting with `Undo` was rejected
  (ADR-0114).
- **Joining while a proposal is open (EP-09-011).** The admission ends by inviting the
  joiner to each open proposal, attributed to the proposer and ledgered; otherwise a
  longer revision lapses the joiner unasked.
- **Visibility.** An invitee's record is born in a ledger entry, so active participants
  see every invitee, declined or silent ones included.

## Removal and reinstatement

Removal withdraws entitlement; it does not delete the record (ADR-0116, CM-31).

| Step | Message | Ledger | Effect |
|---|---|---|---|
| 1 | Case Owner sends `Remove(CaseParticipant, target=Case)` to the CASE_MANAGER | the received `Remove` is the one entry | removal fact set; participant leaves `activeParticipants` |
| 2 | CASE_MANAGER sends the removed party a direct `Remove(CaseParticipant)` naming it | not ledgered | notice only |
| 3 | Removal entry fans out, the removed party included | — | each replica applies the fact by replay; it is the removed party's last entry |
| 4 | Embargo terminated or shortened while it is removed | not sent to it | direct `Remove(EmbargoEvent)` or `Announce(EmbargoEvent)`; its paused replica applies it |
| 5 | Case Owner sends `Add(CaseParticipant, target=Case)` | the received `Add` is the one entry | fact cleared; backfill from the removal entry on (CM-10-006) |

- **Only the Case Owner asks.** The CASE_MANAGER refuses anyone else, and a removal of
  itself or the Case Owner; it never removes on its own. Self-removal is
  `Leave(VulnerabilityCase)`.
- **Consent is untouched.** A removed or departed signatory stays bound and gets the
  direct embargo-ending notices (CM-31-009).
- **Removal is not deletion and not a consent state.** Keep the record in
  `case_participants`; never model removal as a PEC value — an embargo reset would
  erase it, and with no embargo the content gate ignores consent.
- **The fact is `CaseParticipant.removal_activity`** (written by `record_removal`,
  cleared only by `clear_removal`). `VulnerabilityCase.active_participants` applies the
  predicate to inline records; the AS2 dump omits it while any roster entry is a bare
  reference, and persistence never stores it.
- **Removal and reinstatement share one frame.** Both received trees
  (`create_remove_case_participant_received_tree`,
  `create_add_case_participant_received_tree`) run the sender guard the factory
  composes from the declared rule (Case Owner at the manager, CASE_MANAGER at a
  replica, HP-01-008), their admission guard, the guarded
  commit, then CASE_MANAGER-gated effects and notice, built on
  `ParticipantMoveGuardNode` / `ParticipantMoveEffectNode` /
  `EmitParticipantMoveNoticeNode`. Every reinstatement guard failure is `REFUSED`,
  never an idempotent skip. At a replica the received tree writes nothing; the entry is
  replayed by the apply nodes, which resolve the record through
  `actor_participant_index`.
- **`Add(CaseParticipant)` only reinstates** (CM-31-012). It is refused for a
  participant not removed or never joined, and nothing emits it after a stub-Invite
  acceptance: replicas learn of a new member from the entries for the messages
  exchanged (ADR-0114).
- **Catch-up follows the active check.** The reinstatement entry is withheld while the
  participant is still removed and recorded in its pause (`embargo_paused_from_index`);
  `BackfillAdmittedParticipantsNode` then sends every entry from that index, so the
  chain has no gap. A participant reinstated without consent to the active embargo
  stays inert and is re-invited to it (EMB-17-003).
- **A removed participant is asked nothing.** `invitation_recipients` omits it; the
  re-invite and reinstatement Invites check their recipient; both suggest-actor trees
  refuse it before the commit; a replayed `Accept(Invite)` from it is a silent skip in
  `CheckInviteeNotAlreadyParticipantNode`.
- **Embargo-ending notices.** Recipients are `embargo_ending_notice_recipients`; the
  decision is `embargo_ending_notice` (termination before the agreed end owes ET; a
  revision ending no later owes `Announce(EmbargoEvent)`; a longer revision or expiry
  owes nothing). Every CASE_MANAGER path that ends or replaces the embargo brackets its
  EM write with the `embargo_ending_notice_nodes` pair, under the manager gate. One
  activity per recipient, never ledgered. A withheld replica bound by no embargo
  archives the teardown `Announce`, never applies it.

### Entries on the stub Invite path

| What happens | Entry | A replica |
|---|---|---|
| the CASE_MANAGER sends the stub Invite | `invite_actor_to_case` | applies nothing |
| the CASE_MANAGER creates the inert record and puts it on the roster | `create_case_participant` | stores the record carried |
| the invitee sends `Accept(Invite(stub))`: consent signed, joined | `accept_invite_actor_to_case`, the Accept itself | applies the same writes, `updated` = the Accept's `published`; fails if it holds no record |
| VF to `Vf` (VENDOR role only) | `add_participant_status_to_participant` | stores the status |
| the invitee sends `Reject(Invite(stub))`: consent `DECLINED` | `reject_invite_actor_to_case`, the Reject itself | applies the same write |
| the record closes (RM `CLOSED`, vendor `Vf`) | `add_participant_status_to_participant` | stores the status |
| expiry | none | nothing changed (CM-11-014) |

- The CASE_MANAGER and the replica apply the same writes
  (`core/participants/stub_reply.py`), storing what the entry carries; the replica
  derives nothing (ADR-0103, CLP-15-007). The consent row each reply states
  (`joiner_agreement`, `joiner_decline`) is written through the one apply function,
  never by a consent transition on the replica's own row (CM-23-016, #4718).
- Entries are built from the objects the CASE_MANAGER stored, so ids and times match.
- The Accept's VF status is committed after the announce and backfill, so it reaches
  the invitee after its case seed (#2898). Replay from genesis may run over a seed that
  is ahead, so each write moves forward only.
- VF is vendor-only: no other role's record, status or entry carries one.
- Who recommended whom on the `Offer(Actor, Case)` path is not on the case and
  has no entry: it is case bookkeeping, an `ActorRecommendationRecord` in the
  CASE_MANAGER's own store, so no replica holds it (CLP-07-014, #4448).

## Vocabulary: `Offer` versus `Invite`

`Offer` means "take this" (`Offer(VulnerabilityCase)` is ownership transfer); `Invite`
means "take part in this". AS2 defines `Invite` as a specialization of `Offer`. Keep the
distinction in new messages: we accept offers and invitations, never bare objects.

## Pitfalls

- **A joined participant judges the case only by answering the full-case Invite**,
  never the original `Offer(VulnerabilityReport)` or the report triggers (CM-11-020,
  ADR-0121). The check keys on `joined`, not on embargo consent (CM-11-012).
- **A status update never creates a participant.** An on-behalf assertion about a
  non-participant is refused before any write (PRM-06-006).
- **Do not hold the ledger replay until the full-case Invite is accepted.** The history
  is part of what the participant judges, and an `INVALID` participant keeps receiving
  updates (`INVALID` is not `CLOSED`). No readiness handshake: the Accept is the signal,
  and buffering (SYNC-14, SYNC-15) covers the rest.
- **The full-case Invite's ledger position is a floor, not a pin.** The reply carries
  the participant's own position, at or beyond it; pinning would make every reply on a
  busy case stale. The CASE_MANAGER reads the floor from its own stored Invite.
- **A reply's RM move follows the shared declaration rule (RSH-06-006).** Forward moves
  are recorded, backward moves refused before the receipt commit, restatements
  `SKIPPED`; see [received-status-authorization](received-status-authorization.md).
- **A ledger position travels in AS2 `content`**, as the `LedgerPosition` JSON dump
  (VAM-04-011); `target` stays the plain case URI (AKM-02-003). Only
  `vultron.wire.as2.factories.ledger_position_content` writes it, and the extractor
  refuses a missing, blank or non-parsing one. An empty ledger is `logIndex` -1 with
  the case's `genesisHash` (CLP-08-004).
- **Resolve the case from the stub's `caseId`, never its id.** Stub-Invite reply
  patterns match only a `VulnerabilityCaseStub` target; full-case replies have their
  own patterns.
