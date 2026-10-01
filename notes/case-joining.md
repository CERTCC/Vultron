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
related_notes:
  - notes/case-communication-model.md
  - notes/participant-embargo-consent.md
  - notes/participant-role-management.md
  - notes/sync-ledger-replication.md
relevant_packages:
  - vultron/core/behaviors/case/nodes/invite_participant.py
  - vultron/core/behaviors/case/nodes/invite_ledger_backfill.py
  - vultron/core/behaviors/case/nodes/on_behalf_guards.py
  - vultron/core/behaviors/case/nodes/case_participant_received.py
  - vultron/core/behaviors/case/nodes/accept_invite.py
  - vultron/core/models/case.py
  - vultron/core/states/rm.py
  - vultron/wire/as2/vocab/objects/vulnerability_case.py
  - vultron/wire/as2/factories/case.py
---

# Joining a Case — Stub Invite, Inert Participant, Full-Case Invite

The decisions are ADR-0114 (joining, inert participants, the stub type, the
`R → C` transition), ADR-0070 (judging the case) and ADR-0116 (removal and
reinstatement). This note keeps the flow in
one place and records what the earlier model got wrong, because each piece of that model
was internally consistent and the error only showed once all of them were laid
side by side.

## The flow

| Step | Message | RM | VF (vendor) | Embargo consent | Inert? |
|---|---|---|---|---|---|
| 1 | CASE_MANAGER sends `Invite(Actor, VulnerabilityCaseStub)`; record created | `RECEIVED` | `v` | `INVITED` if an embargo is active | yes |
| — | optional on-behalf `v→V` by the Case Manager or Case Owner | — | `V` | — | yes |
| 2a | `Accept(Invite(stub))` — join, and consent to the active embargo | `RECEIVED` | `V` | `SIGNATORY` if an embargo is active | **no** |
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
stub Invite, not removed, RM not `CLOSED`, and — only when an embargo is active —
`SIGNATORY` to it. "Inert until SIGNATORY" is wrong, because many cases have no
active embargo: one not yet established, or one already exited.

Being active is computed by one case-level check from stored facts, and never
stored (CM-31-002). It is a case method, not a participant property: whether an
embargo is active is case state the record cannot see, and a participant-level
"joined" property would read as "active" at a send site.

**Authority to act on a case requires being active.** No situation calls for an
actor to act on a case whose content it may not see. An inert participant's
only messages are its replies to the Invites addressed to it, and those answer
the Invite rather than act on the case. Sender-authority checks (suggesting an
actor, adding a note, rejecting a ledger entry, changing the roster) read the
active check, not roster membership.

## Edge cases

- **Unanswered stub Invite.** It carries a reply deadline; on expiry the
  *Invite* closes as an expired ask and the record stays inert at `RECEIVED`
  (CM-11-014). The CASE_MANAGER never closes an invitee's RM for it, and consent
  stays `INVITED`: the lapse-to-`DECLINED` rule (CM-28-004) is for an expired
  `Invite(EmbargoEvent)`, not for the terms a stub carries.
  "All participants closed" counts only participants that joined.
- **Re-invite.** Same record, fresh stub Invite, new deadline. Refused for a
  participant at `CLOSED` — terminal, no rejoin (CM-11-015, ADR-0085).
- **Embargo changes during the invitation window.** The CASE_MANAGER re-issues
  the stub Invite with current terms; the replacement names the Invite it
  supersedes. `Accept` of a superseded stub is refused with the replacement
  named; `Reject` of it is honoured (CM-11-016). Without this, an invitee
  accepting stale longer terms would join already `LAPSED`.
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
- **Consent is untouched.** A removed `SIGNATORY` stays bound. So does a
  participant that left the case: both get the direct embargo-ending notices
  (CM-31-009), the only messages a removed participant receives besides the
  removal itself.
- **`Add(CaseParticipant)` only reinstates.** It is refused for a participant
  that is not removed or never joined. The CASE_MANAGER no longer emits `Add`
  after a stub-Invite acceptance; replicas learn of a new member from the
  `Accept(Invite)` entry (CM-31-012).
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
returns the whole roster, and nearly every case-content send uses it. CM-10-004
and VP-08-006 (no case content before embargo acceptance) held only because a
non-accepted actor was not in the roster. Putting invitees in the roster without
the filter would have leaked every ledger entry to them. The filter must live in
the shared recipient selection, not at each send site.

**An invitee validated a report it was never offered.** ADR-0070 originally had
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

**Status updates created participants.** ADR-0084 scoped on-behalf `v→V` to a
vendor "not yet — or never — a participant", so the on-behalf tree minted a
participant for an absent target, saved it, and then — for `d→D` — had the RM↔D
entailment refuse the write, leaving a stray record behind. A status update is
never a way into a case.

**The stub and the case were the same thing on the wire.** Same `type`, same
ID; a stub differed only in which fields it carried, so no message could be
about the stub as distinct from the case.

**The RM model could not say "no" from *Received*.** `R → C` did not exist, yet
two paths already closed from other rungs by bypassing the transition table:
`Leave(Case)` through `force_rm_state`, and the report hard-reject. ADR-0114
adds `R → C` only. `V → C` stays out: VP-02-004 forbids closing from *Valid*,
so a `Leave` from `VALID` is recorded as `V → D → C`.

## Vocabulary: `Offer` versus `Invite`

`Offer` means "take this": `Offer(VulnerabilityCase)` is ownership transfer.
`Invite` means "take part in this": both the stub Invite and the full-case
Invite. ActivityStreams defines `Invite` as a specialization of `Offer`, so this
is the vocabulary's own distinction, not one we added. Keep it when a new
message is designed: we accept offers and invitations, never bare objects.

## Pitfalls

- **Roster membership is not "accepted" and not "entitled to content."** Ask
  whether the participant is active.
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
- **Do not add a `TentativeReject` handler for the stub Invite.** It is not a
  valid reply.
