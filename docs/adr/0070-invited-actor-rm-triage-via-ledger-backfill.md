---
status: accepted
date: 2026-10-01
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; CONCERN-2320; CONCERN-4006; ADR-0114;
  specs/case-management.yaml CM-11;
  specs/sync-ledger-replication.yaml SYNC-10
informed: []
stakeholder_type: [project-contributor]
---

# A Joined Participant Judges the Case by Answering a Full-Case Invite, Not the Original Report Offer

## Context and Problem Statement

An actor that joins a case by accepting its stub Invite (ADR-0114) arrives at
RM `RECEIVED`. It then has to judge the case — valid, invalid, or a hard no —
and that judgement is an RM transition that the CASE_MANAGER must record.

The direct report recipient makes the same judgement by answering the reporter's
`Offer(VulnerabilityReport)`: `Accept`, `TentativeReject` or `Reject`. The
question is what a joined participant answers. It never received that Offer,
and what it is presented with is not the original report: it is the case, which
by the time a late joiner arrives holds the report plus everything that built up
during coordination — participants, statuses, embargo history, notes. The
original report might have been far sparser than the case the joiner is asked
to judge.

**What does a joined participant answer to record its judgement of the case?**

## Decision Drivers

- The participant judges what it was shown: the case as it stands, with its
  history, not the original submission.
- We accept offers and invitations, not bare objects. A reply must answer a
  message that was actually sent to the replier.
- `Offer(VulnerabilityCase)` already means ownership transfer; the new message
  must not collide with it in shape.
- The case keeps changing while the participant decides. The record must say
  which version of the case the judgement was about, without making a busy
  case impossible to join.
- RM is the participant's own judgement (ADR-0084). A judgement made with more
  information than was asked for is better informed, not invalid.

## Considered Options

1. **Reuse `validate-report`.** The joined participant finds the reporter's
   original `Offer(VulnerabilityReport)` in the replayed ledger and answers it.
2. **`Announce(VulnerabilityCase)`, answered by `Accept(VulnerabilityCase)`.**
3. **`Offer(VulnerabilityCase)`, answered by `Accept(Offer(VulnerabilityCase))`.**
4. **A full-case Invite: `Invite(Actor, VulnerabilityCase)`, answered by
   `Accept`, `TentativeReject` or `Reject` of that Invite.**

## Decision Outcome

Chosen option: **Option 4 — the CASE_MANAGER invites the participant to the
full case, and the participant's reply is its judgement**, because it answers a
message actually sent to the participant, about the thing the participant was
actually shown, in a shape that collides with nothing.

### The full-case Invite

After the CASE_MANAGER has processed `Accept(Invite(stub))`, it sends the
participant, in this order: `Announce(VulnerabilityCase)`, the ledger replay
(ADR-0114), and then `Invite(Actor, VulnerabilityCase)`. The Invite references
the case by ID and carries no copy of it, because the participant already holds
the case from the Announce. It carries the CASE_MANAGER's **ledger position**
when it issued the Invite: the `log_index` and `entry_hash` of its ledger tail.

The Invite is queued after the last replayed entry. Delivery to each recipient
is ordered (ADR-0112), so the question arrives just as the participant becomes
able to answer it, and nobody waits on anyone: the participant is not holding
an unanswerable question while the history streams in.

The full-case Invite and the stub Invite differ in shape because the stub is
its own type (ADR-0114).

### Its three replies

| Reply | RM message | RM transition |
|---|---|---|
| `Accept(Invite(Actor, VulnerabilityCase))` | RV | `RECEIVED → VALID` |
| `TentativeReject(Invite(Actor, VulnerabilityCase))` | RI | `RECEIVED → INVALID` |
| `Reject(Invite(Actor, VulnerabilityCase))` | RC | `RECEIVED → CLOSED` |

`RECEIVED → CLOSED` is legal because the RM model closes from *Received*
(ADR-0114). After `VALID`, the participant engages or defers exactly as every
other participant does: `Join(VulnerabilityCase)` (RA) and
`Ignore(VulnerabilityCase)` (RD).

A joined participant never sends `Accept`, `TentativeReject` or `Reject` of the
original `Offer(VulnerabilityReport)`: it was never offered that report. That
Offer and its replies belong to the direct report recipient alone.

### The two ledger positions

The Invite's position is a **floor**: "catch up at least this far before you
answer". The reply carries the **participant's own** ledger position when it
decided: the `log_index` and `entry_hash` of its tail. That records what it
actually judged.

The CASE_MANAGER accepts a reply whose position is at or beyond the Invite's and
names an entry its own ledger holds at that index. It refuses a reply behind
the Invite's position, because that participant has not seen what it was asked
to judge, and a reply naming an entry the ledger does not hold, because it is
not a position in this case's history.

The ledger moving between the Invite and the reply is therefore not a race: the
participant answers at its current position, which can never be earlier than
the Invite's. Requiring an answer at exactly the Invite's position would make
every reply on an active case stale and could keep a newcomer from ever
joining.

The existing catch-up gate (SYNC-10-004) already blocks a participant from
protocol-significant case actions until its ledger copy is contiguous from
genesis; the Invite's position gives that gate its target for this reply.

### Consequences

- Good, because the participant answers what it was shown, and a late joiner
  judges the case it actually joined.
- Good, because every reply answers a message sent to the replier; the
  synthetic answer to someone else's Offer goes away.
- Good, because the ledger records which version of the case each judgement was
  about.
- Bad, because a joined participant's path to `VALID` differs from the direct
  report recipient's: two message shapes reach the same RM transition. They are
  answers to different invitations, so the difference is the point, but both
  must be maintained.

## Validation

- A test drives each of the three replies and checks the participant's RM.
- A test asserts a reply behind the Invite's position, or naming an entry the
  ledger does not hold, is refused, and a reply beyond it is accepted.
- A test asserts a joined participant's triage emits no activity whose object
  is the original `Offer(VulnerabilityReport)`.

## Pros and Cons of the Options

### Option 1 — Reuse `validate-report`

The decision this ADR originally recorded (CONCERN-2320).

- Good, because one trigger reaches `VALID` for every participant.
- Bad, because the participant answers an Offer that was never sent to it.
- Bad, because it judges the original report, not the case the participant was
  shown.

### Option 2 — `Announce(VulnerabilityCase)`, answered by `Accept(VulnerabilityCase)`

- Good, because it reuses a message the participant already receives.
- Bad, because `Announce` is informational and nothing in it says an answer is
  expected.
- Bad, because `Accept(VulnerabilityCase)` accepts a bare object.

### Option 3 — `Offer(VulnerabilityCase)`

- Good, because it follows the accept-an-offer pattern.
- Bad, because `Offer(VulnerabilityCase)` already means ownership transfer, and
  `Offer` means "take this", not "take part in this".

### Option 4 — The full-case Invite

- Good, because it asks for an answer, follows the accept-an-invitation
  pattern, and collides with nothing.
- Bad, because it adds a message to the join flow.

## More Information

- ADR-0114 — the join flow this judgement follows: the stub Invite, the inert
  participant, the stub type, and the `R → C` transition.
- CONCERN-2320 — the original question (how an invited actor reaches `VALID`).
- CONCERN-4006 — the planning session that replaced the original answer.
- `notes/case-joining.md` — what the original answer got wrong and why.
