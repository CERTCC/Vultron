---
status: accepted
date: 2026-10-01
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; CONCERN-4006; ADR-0070, ADR-0084, ADR-0093;
  specs/case-management.yaml CM-10, CM-11, CM-23;
  specs/participant-role-management.yaml PRM-06;
  specs/sync-ledger-replication.yaml SYNC-10, SYNC-14, SYNC-15;
  docs/topics/process_models/rm/formal_model.md
informed: []
stakeholder_type: [project-contributor]
---

# Joining a Case: The Invite Creates an Inert Participant, the Stub Is Its Own Type, and RM Closes from *Received*

## Context and Problem Statement

CONCERN-4006 began as a narrow question: an on-behalf `d→D` for a deployer that
had never joined a case was refused, because the on-behalf tree minted a
participant at `RM.START` and the RM↔D entailment refuses `D` there. Working
through it showed that the narrow question sat on top of a misunderstanding of
how an actor joins a case:

1. **The participant record came too late.** A `CaseParticipant` was created
   only when the CASE_MANAGER processed `Accept(Invite)`. Before the invitee
   answered, the case held no record that it had been invited, so the
   CASE_MANAGER could not track the one thing it most needs to: who has been
   told about the case and how they responded. The embargo-consent model
   already has an `INVITED` state, so the design expected the record to exist
   before the reply; the roster did not.
2. **Membership stood in for consent.** Almost every recipient list for
   case-scoped traffic is the whole roster (`case_addressees`). Withholding case
   content from an actor that has not accepted the embargo (CM-10-004, VP-08-006)
   held only because a non-accepted actor was absent from the roster, not
   because any send site checked.
3. **On-behalf status assertions created participants.** ADR-0084 scoped the
   on-behalf `v→V` to a vendor "not yet — or never — a participant", so the
   on-behalf tree minted a participant for an absent target. A status update is
   not a way to join a case.
4. **The stub and the full case were indistinguishable on the wire.**
   `as_VulnerabilityCaseStub` emits `type: "VulnerabilityCase"` and carries the
   case's own ID, so no message can be about "the stub" as distinct from "the
   case".
5. **The RM model could not express a hard no from *Received*.** The published
   transition function has no `R → C`; *Closed* is reachable only from
   *Invalid*, *Accepted* and *Deferred*. Two existing paths already close from
   other rungs by bypassing the table: `Leave(Case)` through the
   `force_rm_state` override (CM-23-012), and the report hard-reject, which
   writes `CLOSED` "regardless of current status". The `Leave` override also
   closes from *Valid*, which VP-02-004 forbids outright.

The question: **how does an actor go from "invited" to "participating" in a
case, what does the case record at each step, and what may it receive?**

How the joined participant then judges the case — the full-case Invite and its
three replies — is ADR-0070. The two decisions are one flow, split so that each
ADR holds one decision.

## Decision Drivers

- The CASE_MANAGER must be able to track an invitee from the moment it is
  invited: whether it has been told, whether it has answered, and how.
- Case content reaches only actors entitled to it. Entitlement is having
  accepted the invitation and, when an embargo is active, being party to it.
  Many cases have no active embargo — not yet established, or already exited —
  so entitlement cannot be "is SIGNATORY" alone.
- A participant's status is self-declaratory (ADR-0084). No other party writes
  a judgement the participant has not made.
- A receiver classifies an activity by its shape. Two messages that mean
  different things must differ in shape, not only in an ID a receiver would
  have to look up.
- We accept offers and invitations, not bare objects. `Offer` means "take
  this" (ownership transfer is `Offer(VulnerabilityCase)`); `Invite` means
  "take part in this". ActivityStreams defines `Invite` as a specialization of
  `Offer` for exactly that sense.

## Considered Options

1. **Keep the record at `Accept(Invite)`; add the missing filters only.**
2. **Create the record at `Invite`; the participant is inert until it is
   entitled to case content; give the stub its own type and ID; add
   `R → C` to the RM model.**
3. **As option 2, but delete the record when the invitee declines.**

## Decision Outcome

Chosen option: **Option 2**, because it lets the CASE_MANAGER track every
invitee from the moment it is invited, makes entitlement to case content an
explicit check instead of a side effect of roster membership, and records only
judgements the participant actually made.

### The participant record is created by the Invite

When the CASE_MANAGER sends `Invite(Actor, VulnerabilityCaseStub)` it creates
the invitee's `CaseParticipant` in the same step, carrying the roles the Invite
names:

| Dimension | Initial value |
|---|---|
| RM | `RECEIVED` |
| VF (VENDOR role only) | `v` |
| Embargo consent | `INVITED` when an embargo is active; otherwise unbound |

This birth is a CASE_MANAGER write through the single participant-status
writer (ADR-0089) and is committed to the case ledger like any other roster
change. It is the one place a vendor participant carries `v`.

### Inert and active

A participant is **active** when both hold:

1. it was seated by the case initialization sequence (CM-14-001) — the Case
   Owner, the CASE_MANAGER and the reporter, none of whom is sent a stub — or it
   has accepted the stub Invite, and
2. no embargo is active, or its embargo consent is `SIGNATORY`.

Every other participant is **inert**. An inert participant exists in the case
for tracking, and receives no case content: no ledger entries, no case
announcements, no status broadcasts, no embargo announcements. The check lives
in the shared recipient selection that every case-content send uses, not at
each send site.

Two kinds of message are addressed to a participant *because* it is not yet
active, and are not case content: the Invites that ask it to join (the stub
Invite) or to consent (an embargo Invite, EP-09). They reach an inert
participant.

A participant can become inert again. An active participant that has not
accepted a newly activated embargo — one whose consent lapses under ADR-0093 —
is no longer entitled to case content until it consents. A participant whose RM
is `CLOSED` has declared it has stopped paying attention, and receives nothing
further either way (CM-23-004). The one exception is the ledger entry that
records its own closure, which is the last thing it receives: it waits for that
entry rather than writing `CLOSED` itself, and its replica never learns of later
closures. Every participant's closure is verified in the CASE_MANAGER's store.

### Replies to the stub Invite

The stub Invite has exactly two replies.

| Reply | Meaning | Record afterwards |
|---|---|---|
| `Accept(Invite(stub))` | Join the case, and consent to the active embargo if there is one. | RM stays `RECEIVED`; VF `V`; consent `SIGNATORY` if an embargo is active. Active. |
| `Reject(Invite(stub))` | A hard no: decline to join. | RM `CLOSED`; VF `V`; consent `DECLINED` if an embargo is active. Kept, inert permanently. |

`TentativeReject` is not a reply to a stub Invite. Accepting the stub is not a
judgement of the case: the invitee has seen only the stub. The judgement comes
after, in reply to the full-case Invite (ADR-0070).

Any reply at all is evidence the vendor is aware, so either reply sets VF `V`.

### An unanswered stub Invite

A stub Invite carries a reply deadline, as an embargo Invite does (CM-28). When
the deadline passes unanswered, the **Invite** expires as an unanswered ask; the
participant's state does not change. The record stays inert at `RECEIVED`,
which records the truth: told, never answered. The CASE_MANAGER cannot close the
invitee's RM for it — RM is the participant's own judgement (ADR-0084) — so a
timeout never stands in for one. That includes embargo consent: it stays
`INVITED`. An expired embargo Invite moves the participant's consent to
`EXPIRED`, not `DECLINED` (CM-28-004, ADR-0118), because silence is not a
refusal; an unanswered stub is not a refusal to join either, and the invitee
may be re-invited on the same record.

Case-wide closure checks ("have all participants closed?") count only
participants that joined. An invitee that never answered does not block
closure.

### Re-inviting

The CASE_MANAGER may re-invite an invitee that has not answered, or whose stub
Invite expired, by sending a fresh stub Invite on the **same** participant
record with a new deadline. An invitee that rejected is at `CLOSED`, which is
terminal with no rejoin (ADR-0085); a re-invite to it is refused.

### The embargo changes while a stub Invite is outstanding

Accepting a stub Invite consents to the embargo terms that stub carried. If the
active embargo changes — activated, revised or terminated — while a stub Invite
is outstanding, an `Accept` of the old stub would consent to terms that no
longer apply: under longer revised terms the participant would join already
`LAPSED`, and under a newly activated embargo it would join without consent,
and in both cases it would have to answer again at once.

So when the active embargo changes while a stub Invite is outstanding, the
CASE_MANAGER **re-issues the stub Invite** with the current terms, on the same
record, with a new deadline. The replacement **names the Invite it
supersedes**, so the invitee knows the old one is dead whichever arrives first.
An `Accept` of a superseded stub Invite is refused, and the refusal names the
replacement. A `Reject` of a superseded stub Invite is still honoured: declining
to join does not depend on the terms. The invitee's single `Accept` therefore
always answers a stub that shows the current embargo state, and nobody joins at
`LAPSED`.

A revision *proposal* is not such a change: it is relayed to the invitee as an
embargo Invite (EP-09-002) like any other non-closed participant. Answering that
Invite records the invitee's consent to the proposed terms and does not join the
case — only an `Accept` of the stub does. If the revision is then activated, the
stub is re-issued as above.

The superseded Invite is **not** retracted with an `Undo`. Correctness does not
depend on a retraction — the refusal already prevents joining on stale terms —
and naming the superseded Invite in its replacement gives the invitee the same
knowledge without a new activity type. Nothing else in the protocol retracts an
ask with `Undo`: proposals cleared by an embargo termination simply stop being
answerable (EP-08-004). See "Pros and Cons" below.

### Joining starts the ledger replay

When the CASE_MANAGER processes `Accept(Invite(stub))` and the participant is
active, it sends the case and replays the case ledger to the participant at
once. No readiness signal from the participant is needed: the Accept is the
signal, out-of-order arrival is buffered (SYNC-14, SYNC-15), and a real gap is
recovered by `Reject(CaseLedgerEntry)` and replay. The case object carries the
current state and the per-case genesis hash, not the ledger entries, so the
replay is what gives the participant the history it then judges.

### The stub is its own type and its own object

`VulnerabilityCaseStub` gets its own wire `type` value (`"VulnerabilityCaseStub"`) and its own ID, the case ID with `/stub` appended.
It names the case it stands for explicitly, in its `caseId` field, so no receiver derives one ID from the other.
What else it carries is CM-17-010: only the embargo terms, and only while an embargo is active.
A stub Invite and a full-case Invite therefore differ in shape and are classified without a lookup.

### On-behalf status targets existing participants only

A status update never creates a participant. The on-behalf assertions of
ADR-0084 target a participant already in the case; an absent target is refused.
For `v→V` that means an inert invitee the CASE_MANAGER or Case Owner has
evidence is aware: the bump changes VF only, never RM.

### RM closes from *Received*

The RM transition function gains one edge, `R → cC`:

$$
\delta^{rm} =
\begin{cases}
S \to rR \\
R \to vV~|~iI~|~cC \\
I \to vV~|~cC \\
V \to aA~|~dD \\
A \to dD~|~cC \\
D \to aA~|~cC \\
C \to \epsilon
\end{cases}
$$

The reply semantics need it: `Reject` means close, and is sent from *Received*
(the stub's hard no, and the hard no to the full-case Invite in ADR-0070).

*Valid* still has no close edge. VP-02-004 forbids closing from *Valid*: a
participant that has found a report valid decides to engage or defer before it
leaves. A `Leave` from `VALID` is therefore recorded as two ordinary
transitions, `V → D → C`, not as an override. With `R → C` in the table and
`Leave` from `VALID` routed through *Deferred*, a `Leave` from any rung and the
report hard-reject are ordinary transitions, and no closure path needs the
`force_rm_state` override.

### Consequences

- Good, because the CASE_MANAGER sees every invitee from the moment it is
  invited, including the ones that decline.
- Good, because entitlement to case content is one explicit check, so adding a
  participant to the roster can no longer leak content by accident.
- Good, because the on-behalf `v→V` has a real job again — marking an inert
  invitee aware — without minting participants.
- Good, because every closure is an ordinary RM transition and two override
  paths go away.
- Bad, because roster membership no longer means "accepted": every roster
  consumer that read it that way — accept-invite idempotency, the join backfill
  guards, embargo-consent cascades, "all participants closed", demo roster
  assertions — must be reviewed.
- Bad, because the RM model no longer matches the RM model of the original
  CERT MPCVD protocol paper (it gains `R → C`); the published formal model, its
  diagrams and every test pinning the transition table change.
- Neutral, because the original report receiver's path (`Offer(Report)` and its
  replies) is unchanged apart from its hard-reject now being a legal
  transition.

## Validation

- A test sends a stub Invite and finds the invitee's participant at `RECEIVED`,
  `v` (vendor) and `INVITED` (active embargo), and finds that no ledger entry or
  case announcement is addressed to it.
- Tests drive each stub reply and check the record against the table above,
  including that `TentativeReject(Invite(stub))` is refused.
- A test asserts every case-content send selects recipients through the shared
  active-participant check (an architecture ratchet).
- A test asserts an on-behalf status update for an absent target is refused and
  leaves the roster unchanged.
- A test lets a stub Invite expire and finds the Invite closed and the record
  unchanged at `RECEIVED`, and finds that an all-participants-closed check
  ignores it.
- A test changes the active embargo while a stub Invite is outstanding and
  finds a replacement stub Invite naming the superseded one, an `Accept` of the
  superseded Invite refused with the replacement named, and a `Reject` of it
  honoured.
- The RM transition table test includes `R → C` and still excludes `V → C`
  (VP-02-004); a `Leave` from `VALID` records `V → D → C`; no closure path
  calls `force_rm_state`.

## Pros and Cons of the Options

### Option 1 — Keep the record at `Accept(Invite)`; add the missing filters only

- Good, because the roster keeps its current meaning and no consumer changes.
- Bad, because the case still has no record of an invitee before it answers,
  which is the tracking gap that started this.
- Bad, because the on-behalf `v→V` still has nothing to target except by
  minting a participant.

### Option 2 — Record at Invite, inert until entitled, stub type, `R → C`

- Good, because every invitee is tracked from the Invite onward.
- Good, because entitlement becomes an explicit, shared check.
- Bad, because it changes what roster membership means, which many consumers
  assumed.

### Option 3 — As option 2, but delete the record on decline

- Good, because the roster after a decline matches today's.
- Bad, because it discards the record that the actor was told and said no,
  which is the history the early record exists to keep.

### Retracting a superseded stub Invite with `Undo`

Considered for the case where the embargo changes while a stub Invite is
outstanding, and rejected.

- Good, because the invitee learns the old Invite is withdrawn from an explicit
  wire message.
- Bad, because it would be the protocol's first retraction message — a new
  pattern to specify, extract and test — for a rare event.
- Bad, because it adds nothing correctness needs: an `Accept` of the superseded
  Invite is refused either way, and the replacement naming the superseded
  Invite tells the invitee the same thing in whichever order the two arrive.

## More Information

- CONCERN-4006 — source; the on-behalf `d→D` refusal that exposed the join model.
- VP-02-004 — no close from *Valid*; why `V → C` was not added.
- ADR-0070 — how an active participant judges the case: the full-case Invite,
  its three replies, and the ledger positions they carry.
- ADR-0084 — participant assertion authority; on-behalf status scoped to
  existing participants.
- ADR-0089 — the single participant-status writer, through which the birth at
  Invite is written.
- ADR-0093 — embargo consent and lapse.
- ADR-0116 — refines this decision's definition of an active participant:
  a participant the Case Owner removed is inert.
- `notes/case-joining.md` — what was misunderstood and why, for readers of the
  old model.
