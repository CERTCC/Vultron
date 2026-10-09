---
title: Joining a Case — Stub Invite, Inert Participant, Full-Case Invite
status: active
description: >
  How an actor goes from invited to participating, what the case records at
  each step, what an inert participant may receive; how removal and reinstatement withdraw and restore entitlement without
  touching membership (ADR-0116). Sources: CONCERN-4006 and CONCERN-2257
  planning sessions (2026-10-01).
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
related_notes:
  - notes/case-communication-model.md
  - notes/embargo-lifecycle.md
  - notes/participant-embargo-consent.md
  - notes/participant-role-management.md
  - notes/sync-ledger-replication.md
  - notes/stub-objects.md
  - notes/wire-core-boundary.md
  - notes/received-status-authorization.md
relevant_packages:
  - vultron/core/participants/recipients.py
  - vultron/core/models/case.py
  - vultron/core/models/case_participant.py
  - vultron/core/behaviors/case/nodes/invite_participant.py
  - vultron/core/behaviors/case/nodes/invite_ledger_backfill.py
  - vultron/core/behaviors/case/nodes/on_behalf_guards.py
  - vultron/core/behaviors/case/nodes/case_participant_received.py
  - vultron/core/behaviors/case/case_participant_received_tree.py
  - vultron/core/behaviors/sync/nodes/participant_removal_effect.py
  - vultron/core/behaviors/case/nodes/participant_reinstatement.py
  - vultron/core/behaviors/embargo/nodes/reinvite.py
  - vultron/core/models/case.py
  - vultron/core/states/rm.py
  - vultron/wire/as2/vocab/objects/vulnerability_case.py
  - vultron/wire/as2/factories/case.py
---

# Joining a Case — Stub Invite, Inert Participant, Full-Case Invite

The decisions are ADR-0114 (joining, inert participants, the stub type, the
`R → C` transition), ADR-0121 (judging the case) and ADR-0116 (removal and
reinstatement). This note keeps the flow in one place.

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

A stub Invite has two replies, not three: there is no `TentativeReject` of a
stub, because accepting a stub is not a judgement of the case.

**Active** means: seated by the case initialization sequence (the Case Owner,
the CASE_MANAGER and the reporter, who are never sent a stub) or accepted the
stub Invite, has not been removed, and — only when an embargo is active —
a signatory to it. "Inert until a signatory" is wrong, because many cases have
no active embargo: one not yet established, or one already exited.

One predicate decides it: `VulnerabilityCase.is_active_participant()`, read
from the replicated `CaseParticipant` record (`joined`,
its consent rows for the active embargo, and the removal fact) and the case's
`active_embargo`, so a replica reaches the same answer as the CASE_MANAGER.
Being active is computed, never stored (CM-31-002): whether an embargo is
active is case state the record cannot see, and a participant-level "joined"
property would read as "active" at a send site. Every case-content send picks
recipients through `vultron/core/participants/recipients.py`:
`case_content_recipients()` for case content, `invitation_recipients()` for the
stub and embargo Invites (inert participants included, RM `CLOSED` excluded,
and removed participants excluded). A roster entry whose
record cannot be read gets nothing (CM-10-007).

RM `CLOSED` is not part of "active", but it ends content delivery all the same
(CM-23-004, ADR-0114; resolved from #4100). A participant at `CLOSED` has
declared it has stopped paying attention, and its replication process is assumed
to have exited, so it is sent no case content (ledger entries, case snapshots,
status broadcasts, embargo announcements). The exception is the entries that
record its own closure, the `close_case` entry and the status entries that follow
it (CM-23-001): it receives every step up to and including the one that reaches
`CLOSED`, and waits for them rather than writing `CLOSED` to its own replica.
Later entries, including `case_fully_closed`, reach only participants whose
closure the ledger does not already record, and a closed replica does not see how
the case ended; that is intended (the same assumption as CM-23-013). The
exception never widens entitlement (a participant that is inert or removed when
it leaves is not sent those entries), and the CM-31-009 embargo notice to a
closed signatory is the only other message a closed participant gets. The
CASE_MANAGER's store is where every participant's closure is verified, so the
demos' "all participants closed" check reads that store. The fan-out code
(`FanOutLogEntryExcludingClosedNode`, `skip_closed=True`) is not yet composed
into the `case_fully_closed` tree, which still reaches every replica; the
implementation issues (#4210, #4212) bring the code to the rule, and
`skip_closed` stops being a variant. The Invites also leave a closed participant
out.

## Authority to act

Authority to act on a case — suggest an actor, add a note, reject a ledger
entry, change the roster — requires an *active* participant. An inert
participant may only reply to the Invites addressed to it: accept or reject the
stub, accept or reject an embargo Invite. A participant at RM `CLOSED` keeps
none of it: it is sent no further Invites and may act on nothing further,
because `CLOSED` is terminal (CM-11-015). It receives only the entry that
records its own closure (see above). The rule is that no actor acts on
a case whose content it may not see; an actor that cannot read the ledger
cannot know what it is acting on, and a CASE_MANAGER that admitted its acts
would commit entries an inert participant could only have guessed at. This
matches the plan for removal in #2257 (PR #4078): removal withdraws
entitlement, not membership, so a removed participant — like an inert one —
keeps its record and loses both its content and its authority. The
CASE_MANAGER itself is held to the predicate as a recipient, with no exemption;
its authority to *commit* comes from its role (CLP-09), not from being active.

## Edge cases

- **Unanswered stub Invite.** It carries a reply deadline, `Invite.end_time`,
  which the CASE_MANAGER stamps exactly as it stamps a relayed embargo Invite's
  (CM-28-012): `published` plus `default_rsvp_window`, floored at
  `min_rsvp_window`, capped at the active embargo's end when one is active. On
  expiry the *Invite* closes as an expired ask and the record stays inert at
  `RECEIVED` (CM-11-014). The CASE_MANAGER never closes an invitee's RM for it,
  and consent stays `INVITED`: the time-out-to-`TIMED_OUT` rule (CM-28-004, #4153)
  is for an expired `Invite(EmbargoEvent)`, not for the terms a stub carries.
  Expiry is read, not recorded: an Invite is expired when `now >= end_time`
  (the embargo Invite's comparison), judged against the CASE_MANAGER's own copy.
  The expiry consequence is *stale* (ASK-03-002, ASK-03-008): expiry only
  means the CASE_MANAGER stops waiting. A late `Accept` still joins and a late
  `Reject` still closes the record. The stale-terms hazard is covered by the
  supersede rule below, not by refusing late replies. A strict mode that
  refuses after expiry is a possible later addition and is not built.
  "All participants closed" counts only participants that joined.
- **Refusals.** The CASE_MANAGER refuses, and writes nothing for: a stub Invite
  with no roles or without a stub summary (CM-11-019, CM-17-010); a
  `Reject` or `Accept` of a stub Invite from an invitee with no participant
  record (CM-11-018, CM-11-021), which is never a silent no-op and never
  creates a participant; and a reply to the full-case
  Invite from an inert participant that has not joined (CM-11-012). Expiry
  writes no participant state and no ledger entry (CM-11-014).
- **Re-invite.** Same record, fresh stub Invite, new deadline, with `inReplyTo`
  set to the earlier stub so the invitee has one live stub. Refused for a
  participant at `CLOSED` — terminal, no rejoin (CM-11-015, ADR-0085) — and for
  one that has already joined. For `CLOSED` the owner's trigger refuses it
  before anything is queued, and the CASE_MANAGER's recommend-actor tree
  refuses an Offer that arrives anyway. For a joined actor the recommend-actor
  tree sends no Invite (the already-participant arm answers instead). The
  Case Owner's `Accept(Offer(CaseParticipant))` is refused for a joined or
  `CLOSED` actor, before the receipt commit (`SuggestedActorIsInvitableNode`,
  CM-16-006), so no second Invite entry reaches the ledger for a record that
  cannot take one. The re-invite arm
  sits ahead of the duplicate arms, because an inert record is on the roster and
  its stub is "in flight" until the invitee answers.
- **Embargo changes during the invitation window.** The CASE_MANAGER re-issues
  the stub Invite with current terms; the replacement names the Invite it
  supersedes. `Accept` of a superseded stub is refused with the replacement
  named; `Reject` of it is honoured (CM-11-016). Without this, an invitee
  accepting stale longer terms would join lapsed. Only an *outstanding* stub is
  re-issued: the invitee has not replied and the newest stub has not expired. An
  expired, unanswered stub waits for a re-invite. The check compares the embargo
  each stub carried with the one a new stub would carry, so it runs after any
  step that may have changed the embargo (the termination, the activation, the
  owner's accept) and does nothing while a proposal is open (EM `PROPOSED` or
  `REVISE`): a proposal alone re-issues nothing.
- **Joining while a proposal is open.** The joiner signs the embargo in force
  (step 2a), but it was not on the roster when the CASE_MANAGER relayed any
  open proposal. The admission therefore ends by inviting it to each open
  proposal, attributed to the original proposer and committed to the ledger
  (EP-09-011); without it a longer revision would lapse the joiner unasked.
- **No `Undo`.** Retracting the superseded Invite was considered and rejected
  (ADR-0114): the refusal already prevents a stale join, and naming the
  superseded Invite in its replacement tells the invitee the same thing in
  either arrival order.
- **Visibility.** The birth of an invitee's record is a ledger entry, so active
  participants see invitees — including ones that declined or never answered —
  in their replica of the roster.

## Removal and reinstatement

Removal withdraws entitlement; it does not delete the record (ADR-0116, CM-31).

| Step | Message | Ledger | Effect |
|---|---|---|---|
| 1 | Case Owner sends `Remove(CaseParticipant, target=Case)` to the CASE_MANAGER | the received `Remove` is the one entry | removal fact set; participant leaves `activeParticipants` |
| 2 | CASE_MANAGER sends the removed party a direct `Remove(CaseParticipant)` naming it | not ledgered | notice only |
| 3 | Removal entry fans out, the removed party included | — | each replica applies the fact by replay; it is the removed party's last entry |
| 4 | Embargo terminated or shortened while it is removed | not sent to it | direct `Remove(EmbargoEvent)` or `Announce(EmbargoEvent)`; its paused replica applies it |
| 5 | Case Owner sends `Add(CaseParticipant, target=Case)` | the received `Add` is the one entry | fact cleared; backfill from the removal entry on (CM-10-006) |

- **Only the Case Owner asks.** The CASE_MANAGER refuses a request from anyone
  else, and a removal of itself or of the Case Owner. It never removes on its
  own initiative. Self-removal is `Leave(VulnerabilityCase)`.
- **Consent is untouched.** A removed signatory stays bound. So does a
  participant that left the case: both get the direct embargo-ending notices
  (CM-31-009), the only messages a removed participant receives besides the
  removal itself.
- **`Add(CaseParticipant)` only reinstates.** It is refused for a participant
  that is not removed or never joined. The CASE_MANAGER no longer emits `Add`
  after a stub-Invite acceptance; replicas learn of a new member from the
  entries the CASE_MANAGER commits for each change it makes (CM-31-012).
- **Where the fact and the check live (#4079).** The fact is
  `CaseParticipant.removal_activity`: the id of the `Remove` activity, or
  `None` (`removed` reads it). The one check is
  `VulnerabilityCase.is_active_participant`, which the shared recipient
  selection calls. `VulnerabilityCase.active_participants` (`activeParticipants`
  on the wire) applies it to the participant records the case carries inline,
  so it is complete on a case as sent. While any roster entry is a bare
  reference (a stored case), the AS2 dump leaves it out rather than publish a
  partial view. Persistence never stores it.
- **Where the removal pipeline lives (#4080).** The received tree is
  `create_remove_case_participant_received_tree`: a role-scoped sender guard
  (Case Owner at the manager, CASE_MANAGER at a replica), the three removal
  guards behind `case_manager_admits_removal_guard`, the guarded commit, then
  the CASE_MANAGER-gated effect (`RemoveCaseParticipantFromCaseReceivedNode`,
  via `CaseParticipant.record_removal`) and notice
  (`EmitParticipantRemovalNoticeNode`, port method
  `remove_participant_from_case`). Replicas replay the entry through
  `ApplyRemoveCaseParticipantFromLedgerNode`, which resolves the record by
  actor through `actor_participant_index`. At a replica the received tree
  writes nothing: the manager's notice is `SKIPPED`, anyone else's `Remove` is
  `REFUSED`.
- **Where the reinstatement pipeline lives (#4081).** It mirrors removal
  piece by piece. `create_add_case_participant_received_tree` runs the same
  role-scoped sender guard, then `case_manager_admits_reinstatement_guard`
  (names a participant, `ParticipantHasJoinedNode`, `ParticipantIsRemovedNode`;
  every failure is `REFUSED`, none is an idempotent skip), the guarded commit,
  and the CASE_MANAGER-gated effects in
  `core/behaviors/case/nodes/participant_reinstatement.py`:
  `ReinstateCaseParticipantReceivedNode` (via `CaseParticipant.clear_removal`,
  the one clearing write), `BackfillAdmittedParticipantsNode`,
  `EmitParticipantReinstatementNoticeNode` (port method
  `add_participant_to_case`, which now takes `attributed_to`) and
  `InviteReinstatedParticipantToEmbargoNode`. The guard, effect and notice
  frames (`ParticipantMoveGuardNode`, `ParticipantMoveEffectNode`,
  `EmitParticipantMoveNoticeNode`) and the use case frame are shared with
  removal. Replicas replay the entry through
  `ApplyReinstateCaseParticipantFromLedgerNode`, which shares its record
  lookup with the removal apply node.
- **Catch-up follows the active check (#4084).** The reinstatement entry's
  fan-out is selected while the participant is still removed, so it is
  withheld and recorded in that peer's pause (`embargo_paused_from_index`,
  set by the first entry withheld after the removal entry). Once the fact is
  cleared, `BackfillAdmittedParticipantsNode` sends every entry from that
  index on, the reinstatement entry included, so the replica's chain joins
  with no gap. A participant reinstated into a case whose embargo it has not
  accepted stays inert: `InviteReinstatedParticipantToEmbargoNode` sends it
  the active embargo's Invite (the EMB-17-003 re-invite frame, committed as
  `invite_to_embargo_on_case_reinvite`), and the embargo-acceptance tree's
  own backfill admits it when it consents.
- **A removed participant is asked nothing (#4084).** `invitation_recipients`
  leaves it out, so no embargo Invite or revision relay reaches it; the
  EMB-17-003 re-invite and the reinstatement Invite check their one recipient
  against it too. Both suggest-actor trees refuse a recommendation of it, and
  the Case Owner's acceptance of an earlier one, before the commit
  (`case_manager_admits_suggested_actor_guard`), so no stub Invite reaches
  it. A replayed `Accept(Invite)` from it is a silent skip in
  `CheckInviteeNotAlreadyParticipantNode`: no case seed, backfill or
  full-case Invite.
- **No `Add` after a stub-Invite acceptance (#4081).** Neither the
  accept-invite tree nor the recommend-actor trees emit `Add(CaseParticipant)`
  or commit `add_case_participant`; `EmitAddCaseParticipantNode` is deleted.
  Every state change the CASE_MANAGER makes emits its own entry (ADR-0114), so
  one trigger can produce several, and a replica stores what each carries, as
  received (ADR-0103, CLP-15-007). It derives nothing.
- **One entry per change on the stub Invite path (#4384).**

  | Change by the CASE_MANAGER | Entry | A replica |
  |---|---|---|
  | sends the stub Invite | `invite_actor_to_case` | applies nothing |
  | creates the inert record and puts it on the roster | `create_case_participant` | stores the record carried, and seats it |
  | accepts: signs the consent row, marks joined | `update_case_participant` | copies `joined`, the consent rows and `updated`; fails if it holds no record |
  | accepts: VF to `Vf` (VENDOR role only) | `add_participant_status_to_participant` | stores the status carried |
  | rejects: RM `CLOSED` (and `Vf` for a vendor) | `add_participant_status_to_participant` | stores the status carried |
  | rejects: consent `DECLINED` | `update_case_participant` | copies the consent rows and `updated` |
  | expiry | none | nothing changed (CM-11-014) |

  The entries are built from the very objects the CASE_MANAGER stored, so ids
  and times match: `commit_case_participant_created`, `..._updated` and
  `commit_participant_status_added` in `case/participant_ledger.py` render the
  stored record. A record born at the Invite is one entry carrying the record,
  its birth status and its consent rows, as `Create(VulnerabilityCase)` carries
  a case. The Accept's entries are committed by `CommitInviteeAcceptEntriesNode`
  after the announce and the backfill, so they reach the invitee in chain order
  and not before its case seed (#2898), then the full-case Invite follows. VF is
  a vendor-only status: no other role's record, status or entry carries one. The
  two-replica test compares the whole record of the CASE_MANAGER and each
  replica after the Invite, the Accept and the Reject, for a vendor, a
  non-vendor, and a case with and without an embargo in force. Not entries
  today: `case.recommendation_recommender_index` set on the `Offer(Actor, Case)`
  path, whose receipt entry carries the same fact but no replica applies it
  (#4295).
- **Where the embargo-ending notices live (#4083).** The recipients are
  `embargo_ending_notice_recipients` (joined, a signatory to the ending
  embargo, removed or RM `CLOSED`). The decision is `embargo_ending_notice`:
  a termination before the agreed end owes ET; a revision that ends no later
  (the EP-05-001 carry-over arm, ties included) owes `Announce(EmbargoEvent)`;
  a longer revision or an expiry owes nothing. Every path that ends or
  replaces the embargo at the CASE_MANAGER brackets its EM write with the pair
  from `embargo_ending_notice_nodes` (`CaptureActiveEmbargoNode` before,
  `SendEmbargoEndingNoticesNode` after, under the manager gate): the received
  `Remove`/`Add(EmbargoEvent)`, the owner's received `Accept` of a revision,
  `terminate_embargo_bt` (trigger, P/X/A cascade, owner EJ after disclosure)
  and the trigger answer arms. One activity per recipient, never ledgered,
  `attributedTo` the requester when it is not the manager. At the replica,
  the received `Remove(EmbargoEvent)` tree applies ET through
  `EmbargoLifecycle`; a replica owed a notice (`AwaitsEmbargoEndingNoticeNode`,
  `awaits_embargo_ending_notice`: the same recipient rule, read about itself)
  applies an announced shorter revision through
  `ApplyAnnouncedEmbargoRevisionNode` (`activate_embargo`, `OBSERVED`). A
  withheld replica is paused but bound by no embargo in force, so the
  teardown `Announce` that reaches it is archived, never applied. The
  sender guard admits only the CASE_MANAGER. The teardown `Announce` itself
  skips RM `CLOSED` participants (CM-23-004). Until #4212 lands, a closed
  signatory still receives fan-out and so gets both the entry and the notice;
  both apply idempotently.

## Vocabulary: `Offer` versus `Invite`

`Offer` means "take this": `Offer(VulnerabilityCase)` is ownership transfer.
`Invite` means "take part in this": both the stub Invite and the full-case
Invite. ActivityStreams defines `Invite` as a specialization of `Offer`, so this
is the vocabulary's own distinction, not one we added. Keep it when a new
message is designed: we accept offers and invitations, never bare objects.

## Pitfalls

- **Roster membership is not "accepted" and not "entitled to content."** Ask
  whether the participant is active: it accepted the stub Invite, has not been
  removed, and — only while an embargo is active — is a signatory to it. The
  check lives in the shared recipient selection, never at a send site
  (CM-10-004, CM-10-005).
- **A joined participant never answers the original `Offer(VulnerabilityReport)`**
  and never runs `validate-report`/`invalidate-report`/`reject-report` for the
  case's report; it judges the case by answering the full-case Invite
  (CM-11-020, ADR-0121).
- **A status update never creates a participant.** An on-behalf assertion whose
  target is not a participant is refused before any write (PRM-06-006).
- **Removal is not deletion and not a consent state.** Do not drop a removed
  participant from `case_participants`, and do not model removal as a PEC
  value: an embargo reset would erase it, and with no embargo the content gate
  ignores consent entirely.
- **Do not hold the ledger replay until the full-case Invite is accepted.** A
  participant is active once it accepts the stub; the history is part of what
  it judges, and a participant that finds the case `INVALID` keeps receiving
  updates (`INVALID` is not `CLOSED`).
- **No readiness handshake before the replay.** The Accept is the signal;
  buffering (SYNC-14, SYNC-15) and reject-and-replay cover the rest.
- **The full-case Invite's ledger position is a floor, not a pin.** The reply
  carries the participant's own position, at or beyond the Invite's. Pinning
  the reply to the Invite's position would make every reply on a busy case
  stale.
- **Only a joined participant may judge the case.** A reply to the full-case
  Invite from a participant whose record is not `joined` (an inert
  participant) is refused with a reported reason and writes no ledger entry
  (CM-11-012); the check keys on the same `joined` fact as
  `is_active_participant()`, not on embargo consent.
- **A reply's RM move is judged by the shared declaration rule, not
  adjacency (RSH-06-006, #4311).** A second or later reply that moves forward,
  a non-adjacent move included, is recorded; one that moves backward is
  refused before the receipt is committed; one that restates the recorded
  state is `SKIPPED`. See
  [received-status-authorization.md](received-status-authorization.md).
- **A ledger position travels in AS2 `content`, as the `LedgerPosition`
  model's own JSON dump.** The full-case Invite and each reply carry
  `{"logIndex":3,"entryHash":"..."}` (VAM-04-011..014); `target` stays the
  plain case URI (AKM-02-003), and no AS2 verb gains a field. An empty ledger
  is `logIndex` -1 with the case's `genesisHash` (CLP-08-004). Only
  `vultron.wire.as2.factories.ledger_position_content` writes it, and the
  extractor parses it at the edge and refuses a missing, blank or
  non-parsing one. The CASE_MANAGER reads the floor from its own stored
  Invite, never from the copy a reply embeds.
- **Do not add a `TentativeReject` handler for the stub Invite.** It is not a
  valid reply.
- **Resolve the case from the stub's `caseId`, never its ID.** Since #4045 the
  stub-Invite reply patterns match only a `VulnerabilityCaseStub` target, so a
  reply to a full-case Invite is told apart by its plain case-URI target
  (#4050 added its own patterns).
- **`Reject(Invite(stub))` with no participant record must be REFUSED, not
  treated as a no-op (CM-11-018).** The CASE_MANAGER must hold an inert
  participant record (created at invite-send time, ADR-0114) before it can
  apply the Reject. If no such record exists the result is REFUSED with the
  reason "no invited participant record". Silently succeeding hides protocol
  violations: either the original stub Invite was never sent, or the inert
  record was lost. Both are errors.
- **A stub Invite with no roles must be refused at emit time; never default to
  VENDOR (CM-11-019).** `EvaluateDefaultRolesNode` returns `[]` — not
  `[CVDRole.VENDOR]` — when no roles are specified. An empty list propagates to
  `Status.FAILURE`, which the trigger path converts to REFUSED with a message
  saying "inviter must give the invitee's roles". Defaulting to VENDOR was the
  original lenient choice; it has been overruled. A second guard in
  `CreateInertInviteeParticipantNode` enforces the same rule as
  defence-in-depth at inert-record creation time.
