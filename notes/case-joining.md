---
title: Joining a Case — Stub Invite, Inert Participant, Full-Case Invite
status: active
description: >
  How an actor goes from invited to participating, what the case records at
  each step, what an inert participant may receive, and what the old model got
  wrong. Source: CONCERN-4006 planning session (2026-10-01).
related_specs:
  - specs/case-management.yaml
  - specs/participant-role-management.yaml
  - specs/rm-behavior.yaml
  - specs/vultron-as2-mapping.yaml
  - specs/participant-case-replica.yaml
  - specs/sync-ledger-replication.yaml
  - specs/case-ledger-processing.yaml
  - specs/embargo-policy.yaml
related_notes:
  - notes/case-communication-model.md
  - notes/participant-embargo-consent.md
  - notes/participant-role-management.md
  - notes/sync-ledger-replication.md
relevant_packages:
  - vultron/core/participants/recipients.py
  - vultron/core/behaviors/case/nodes/invite_participant.py
  - vultron/core/behaviors/case/nodes/invite_ledger_backfill.py
  - vultron/core/behaviors/case/nodes/on_behalf_guards.py
  - vultron/core/models/case.py
  - vultron/core/states/rm.py
  - vultron/wire/as2/vocab/objects/vulnerability_case.py
  - vultron/wire/as2/factories/case.py
---

# Joining a Case — Stub Invite, Inert Participant, Full-Case Invite

The decisions are ADR-0114 (joining, inert participants, the stub type, the
`R → C` transition) and ADR-0070 (judging the case). This note keeps the flow in
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
stub Invite, and — only when an embargo is active — `SIGNATORY` to it.
"Inert until SIGNATORY" is wrong, because many cases have no active embargo:
one not yet established, or one already exited.

One predicate decides it: `VulnerabilityCase.is_active_participant()`, read
from the replicated `CaseParticipant` record (`joined`,
`embargo_consent_state`) and the case's `active_embargo`, so a replica reaches
the same answer as the CASE_MANAGER. Every case-content send picks recipients
through `vultron/core/participants/recipients.py`: `case_content_recipients()`
for case content, `invitation_recipients()` for the stub and embargo Invites
(inert participants included, RM `CLOSED` excluded). A roster entry whose
record cannot be read gets nothing (CM-10-007).

RM `CLOSED` is not part of "active". ADR-0114 says a closed participant
"receives nothing further", and CM-23-004 says ledger fan-out skips it, but the
`case_fully_closed` fan-out deliberately reaches every replica whatever its RM
state, and a departing participant learns its own `CLOSED` only from the
ledger entry that records it (the sender side does not write it). Applying the
exclusion to every case-content send would leave a closed replica unable to
see how the case ended. Only `skip_closed=True` (CM-23-004's own fan-out
variant) and the Invites leave a closed participant out. #4100 tracks
reconciling the two rules.

## Authority to act

Authority to act on a case — suggest an actor, add a note, reject a ledger
entry, change the roster — requires an *active* participant. An inert
participant may only reply to the Invites addressed to it: accept or reject the
stub, accept or reject an embargo Invite. A participant at RM `CLOSED` keeps
none of it: it is sent no further Invites and may act on nothing further,
because `CLOSED` is terminal (CM-11-015). It may still *receive* the entries
that close out its replica (see above). The rule is that no actor acts on
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
  whether the participant is active.
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
