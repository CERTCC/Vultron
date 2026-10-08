---
title: Joining a Case — Stub Invite, Inert Participant, Full-Case Invite
status: active
description: >
  How an actor goes from invited to participating, what the case records at
  each step, what an inert participant may receive, and what the old model got
  wrong; how removal and reinstatement withdraw and restore entitlement without
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
  - vultron/core/behaviors/case/nodes/accept_invite.py
  - vultron/core/models/case.py
  - vultron/core/states/rm.py
  - vultron/wire/as2/vocab/objects/vulnerability_case.py
  - vultron/wire/as2/factories/case.py
---

# Joining a Case — Stub Invite, Inert Participant, Full-Case Invite

The decisions are ADR-0114 (joining, inert participants, the stub type, the
`R → C` transition), ADR-0121 (judging the case) and ADR-0116 (removal and
reinstatement). This note keeps the flow in
one place and records what the earlier model got wrong, because each piece of that model
was internally consistent and the error only showed once all of them were laid
side by side.

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
its consent rows for the active embargo, and the removal fact once #4079 lands) and the case's
`active_embargo`, so a replica reaches the same answer as the CASE_MANAGER.
Being active is computed, never stored (CM-31-002): whether an embargo is
active is case state the record cannot see, and a participant-level "joined"
property would read as "active" at a send site. Every case-content send picks
recipients through `vultron/core/participants/recipients.py`:
`case_content_recipients()` for case content, `invitation_recipients()` for the
stub and embargo Invites (inert participants included, RM `CLOSED` excluded,
and removed participants excluded once #4084 lands). A roster entry whose
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

- **Unanswered stub Invite.** It carries a reply deadline; on expiry the
  *Invite* closes as an expired ask and the record stays inert at `RECEIVED`
  (CM-11-014). The CASE_MANAGER never closes an invitee's RM for it, and consent
  stays `INVITED`: the time-out-to-`TIMED_OUT` rule (CM-28-004) is for an expired
  `Invite(EmbargoEvent)`, not for the terms a stub carries.
  "All participants closed" counts only participants that joined.
- **Re-invite.** Same record, fresh stub Invite, new deadline. Refused for a
  participant at `CLOSED` — terminal, no rejoin (CM-11-015, ADR-0085).
- **Embargo changes during the invitation window.** The CASE_MANAGER re-issues
  the stub Invite with current terms; the replacement names the Invite it
  supersedes. `Accept` of a superseded stub is refused with the replacement
  named; `Reject` of it is honoured (CM-11-016). Without this, an invitee
  accepting stale longer terms would join lapsed.
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
  `Accept(Invite)` entry (CM-31-012).
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
  `REFUSED`. Reinstatement (#4081) mirrors each piece.
- **Catch-up follows the active check.** A participant reinstated into a case
  whose embargo it has not accepted stays inert; it is sent that embargo's
  Invite, and its backfill waits for its consent.

## What the old model got wrong

**The participant record came after the reply.** `CaseParticipant` was created
when the CASE_MANAGER processed `Accept(Invite)`. The case therefore held no
record of an invitee that had not answered — or that declined — which is
exactly what the CASE_MANAGER needs to track. The embargo-consent model's
`INVITED` state already assumed a pre-reply record.

**Roster membership was doing the job of the consent check.** `case_addressees`
returned the whole roster, and nearly every case-content send used it. CM-10-004
and VP-08-006 (no case content before embargo acceptance) held only because a
non-accepted actor was not in the roster. Putting invitees in the roster without
the filter would have leaked every ledger entry to them. The filter now lives in
the shared recipient selection, not at each send site, and `case_addressees` is
gone (#4046).

**An invitee validated a report it was never offered.** ADR-0121 originally had
the invitee recover the reporter's `Offer(VulnerabilityReport)` from the ledger
replay and answer it with the standard `validate-report`. Two things are wrong
with that. A reply must answer a message sent to the replier. And the joiner
judges the *case* — for a late joiner, the report plus everything that built up
during coordination — not the original submission, which may have been far
sparser.

**`Accept(Invite)` was read as joining only, while the wire factories labelled
it RV.** CM-11-001 said `Accept(Invite)` leaves RM at `RECEIVED`; the factory
docstrings called it the RV message and `Reject(Invite)` the RI message. Both
were half right: there are two Invites. Accepting the stub is joining (no RM
move); accepting the full-case Invite is RV.

**Status updates created participants.** The original ADR-0084 scoped
on-behalf `v→V` to a vendor "not yet — or never — a participant", so the on-behalf tree minted a
participant for an absent target, saved it, and then — for `d→D` — had the RM↔D
entailment refuse the write, leaving a stray record behind. A status update is
never a way into a case.

**The stub and the case were the same thing on the wire.** Same `type`, same
ID; a stub differed only in which fields it carried, so no message could be
about the stub as distinct from the case. Fixed in #4045: the stub is
`VulnerabilityCaseStub` with ID `<case-id>/stub` and a `caseId` naming the case
(CM-11-013), and it carries only that plus the embargo terms (CM-17-010).

**The RM model could not say "no" from *Received*.** `R → C` did not exist, yet
two paths already closed from other rungs by bypassing the transition table:
`Leave(Case)` through `force_rm_state`, and the report hard-reject. ADR-0114
adds `R → C` only. `V → C` stays out: VP-02-004 forbids closing from *Valid*,
so a `Leave` from `VALID` is recorded as `V → D → C`. Both landed in #4044, which
also retired the closure uses of `force_rm_state` and guarded the hard-reject.

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
  (CM-11-018, ADR-0121).
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
