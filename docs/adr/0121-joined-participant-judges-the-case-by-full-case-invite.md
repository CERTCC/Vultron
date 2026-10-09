---
status: accepted-provisional
date: 2026-10-06
created: 2026-10-06
updated: 2026-10-06
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Sonnet 5.5; CONCERN-2320; CONCERN-4006; CONCERN-2087; ADR-0114;
  specs/case-management.yaml CM-11; specs/participant-role-management.yaml PRM-06;
  the 2026-10-02 audit of unsupervised agent decisions (#4195)
supersedes: 0070-invited-actor-rm-triage-via-ledger-backfill.md
informed: []
stakeholder_type: [project-contributor]
---

# A Joined Participant Judges the Case by Answering a Full-Case Invite; Status Is Self-Declared and Asserted Only for Existing Participants

## Context and Problem Statement

This ADR carries the 2026-10-01 decisions of CONCERN-4006 that replaced two accepted ADRs, both of which had been rewritten in place under their own numbers: ADR-0070 (how an invited actor reaches `VALID`) and ADR-0084 (participant assertion authority).
Their original texts are restored and marked superseded by this ADR, and the 2026-10-01 text now lives here.
The two decisions are one flow: the first is what a joined participant answers, the second is which participants a status write may target.

### Decision A — judging the case

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

### Consequences of Decision A

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

### Decision B — participant status is self-declared, asserted on behalf only for existing participants

The rules of ADR-0084 that are unchanged by the 2026-10-01 decision are restated here so that this ADR is self-contained.
ADR-0084 weighed three options (strictly self-reported with no exceptions; a general on-behalf proxy for the Case Manager or Case Owner; self-declared with narrow externally evidenced exceptions) and chose the third; that choice is unchanged.
The change is the first rule: **on-behalf assertions target existing participants only**, and joining a case is the Invite flow of ADR-0114.

  own RM and VFD state; no approval is required. This is why they are
  *participant* status items.

- **On-behalf assertions target existing participants only.** A status
  update never creates a participant; an on-behalf assertion whose target is
  not a participant in the case is refused. Joining a case is the Invite flow
  (ADR-0114), and the Invite is what creates the participant record.
- **`v→V` (vendor aware) MAY be asserted on behalf of a Vendor-role
  participant** by a Case Manager or Case Owner, because the notification event
  is itself observable evidence. Any acknowledgement from the vendor of any
  message sent to it — even a `Read(Invite(stub))` — is sufficient evidence.
  The bump changes VF only, never RM.
- **`d→D` (fix deployed) MAY be asserted on behalf of a Deployer-role
  participant** by a Case Manager or Case Owner under the same
  externally-evidenced pattern, but only in exceptional circumstances (a MAY,
  expected to be rare; for example, a deployer that joined and has since gone
  quiet). Deployment is normally self-reported by the Deployer. The write is
  still subject to the cross-machine entailments, so it succeeds only for a
  deployer whose RM is consistent with deployment.
- **`f→F` (fix ready) is Vendor-only, always self-reported.** It is not
  externally knowable; no on-behalf assertion is ever permitted.
- **Role and roster changes require Case Owner approval** via the existing
  CaseActor-routed Offer/Accept pattern (ADR-0026). Nothing here relaxes that.

#### When a vendor participant may be at `v`

A Vendor that has answered its Invite, or that has otherwise acknowledged any
message about the case, is aware of the case. The Invite creates the vendor's
participant record at VF `v` before it has answered (ADR-0114), and that record
is the only place a vendor participant carries `v`. Therefore:

- A Vendor-role participant never self-reports `v`: its only valid VF
  self-reports are `Vf` and `VF`.
- Any reply to the Invite sets `V`.
- The on-behalf `v→V` assertion is the mechanism for recording awareness of an
  invited vendor that has not answered: it targets that inert participant
  record, so the CASE_MANAGER can track pre-join awareness without minting
  anything.

This invariant is enforceable and always an error to violate, so it belongs in
the consolidated rule layer (`vultron/core/predicates/`, CONCERN-3020), not
inline at each assertion site.

### Consequences of Decision B

- Good: the vendor-awareness gap (CONCERN-2087) closes without a general proxy
  authority for the Case Actor, and without minting participants.
- Good: `f→F` remains unforgeable; only the vendor can claim fix readiness.
- Bad: the Vendor-implies-V invariant must be added to the rule layer and every
  existing Vendor VF assertion site checked against it.

## Validation

- A test drives each of the three replies and checks the participant's RM.
- A test asserts a reply behind the Invite's position, or naming an entry the
  ledger does not hold, is refused, and a reply beyond it is accepted.
- A test asserts a joined participant's triage emits no activity whose object
  is the original `Offer(VulnerabilityReport)`.
- A test asserts an on-behalf assertion for an actor that is not a participant
  is refused and leaves the roster unchanged.
- A rule-layer test asserts a Vendor-role participant cannot self-report a VF
  state with `v` set (valid Vendor VF self-reports ∈ {Vf, VF}).
- A test asserts `f→F` is rejected when asserted by any actor other than the
  Vendor-role holder.

## Pros and Cons of the Options

### Option 1 — Reuse `validate-report`

The decision ADR-0070 originally recorded (CONCERN-2320).

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

- ADR-0070 and ADR-0084 — superseded by this ADR; their original texts are
  restored in `docs/adr/archived/`.
- ADR-0026 — role authority; ADR-0080 — the owner-approval mechanism;
  ADR-0085 — case lifecycle boundaries (companion to ADR-0084).
- CONCERN-2087, CONCERN-3020, CONCERN-2833 — the vendor-awareness gap, the
  rule layer, and the planning session behind ADR-0084.
- ADR-0114 — the join flow this judgement follows: the stub Invite, the inert
  participant, the stub type, and the `R → C` transition.
- CONCERN-2320 — the original question (how an invited actor reaches `VALID`).
- CONCERN-4006 — the planning session that replaced the original answer.
- `notes/case-joining.md` — what the original answer got wrong and why.
