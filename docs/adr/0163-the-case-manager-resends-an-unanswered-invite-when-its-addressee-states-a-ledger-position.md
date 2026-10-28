---
status: proposed
date: 2026-10-28
created: 2026-10-28
updated: 2026-10-28
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0065, ADR-0155, ADR-0156, ADR-0161;
  specs/case-bootstrap-trust.yaml CBT-03; specs/case-management.yaml CM-23-016;
  specs/sync-ledger-replication.yaml
  SYNC-15-012, SYNC-15-013, SYNC-17, SYNC-18-002, SYNC-18-007, SYNC-19-003;
  specs/embargo-policy.yaml EP-09-002, EP-09-011; specs/case-management.yaml
  CM-11-010, CM-31-013; issues #5204, #5320
informed: []
stakeholder_type: [project-contributor]
---

# The Case Manager Resends an Unanswered Invite When Its Addressee States a Ledger Position

## Context and Problem Statement

A participant that joins a case receives its case copy, the prior ledger, the full-case Invite and an `Invite(EmbargoEvent)` for each open embargo proposal (CM-11-008, CM-11-010, EP-09-011).
The CASE_MANAGER queues them in that order, but the transport promises no delivery order (SYNC-19-003, [ADR-0161](0161-eventual-consistency-is-the-protocols-ordering-guarantee.md)).
An Invite that reaches the joiner before its case copy waits in the joiner's pre-bootstrap queue (CBT-03-001).
If the case copy takes longer than the queue's window, 300 seconds by default (CBT-03-005), the Invite is dropped (CBT-03-003).
A reinstatement Invite (CM-31-013) can be dropped the same way.

Nothing resends a dropped Invite.
The receiver's replay `Question` (CBT-03-004) has no handler on the CASE_MANAGER, and it asks for `Create(VulnerabilityCase)`, which no longer delivers a case copy (PCR-02-005).
The ledger does not help either: the replica copies the entry that records the Invite's emission, but applying an entry runs no lifecycle logic (CM-23-016), so nothing prompts the joiner to answer.
A joiner whose embargo Invite was dropped never answers, its consent row times out and it lapses.
A joiner whose full-case Invite was dropped has nothing to reply to, so it cannot judge the case.

How does an Invite dropped before the case copy reach its addressee again?

## Decision Drivers

- The protocol meant the joiner to have a chance to consent (EP-09-011); losing that chance to delivery timing defeats the requirement.
- A decision must not depend on arrival order the ledger does not define (SYNC-19-001).
- Vultron's core has no scheduler; time-driven decisions run when an activity arrives (CLP-10-025).
- A resent activity carries the ledger position it was first sent with (SYNC-18-002), and a receiver treats a redelivery of an activity it already handled as a no-op (IE-10-001).
- The CASE_MANAGER already learns where a participant stands from its position statements (SYNC-17, SYNC-18-007, [ADR-0155](0155-a-participant-states-its-ledger-position-and-the-case-manager-answers-a-lag.md)).

## Considered Options

- Accept the window as a bound and record that a dropped Invite is lost.
- Make the receiver's replay `Question` work: the CASE_MANAGER answers it with the case copy and any Invite the sender owes an answer to.
- The CASE_MANAGER resends each Invite a participant owes an answer to whenever that participant states its ledger position.
- Hold pre-bootstrap messages with no time limit.

## Decision Outcome

Chosen option: "The CASE_MANAGER resends each Invite a participant owes an answer to whenever that participant states its ledger position", because a position statement is the first sign the CASE_MANAGER gets that the replica holds the case, it reuses an answer path that exists, and it needs neither a scheduler nor the receiver's lazy queue expiry.

- **The trigger is a position statement.** When the CASE_MANAGER acts on a ledger position stated by an active participant, in `Read(CaseLedgerEntry)` or in an activity's `ledgerPosition` (SYNC-17-002, SYNC-18-007), it resends each Invite that participant owes an answer to.
- **An Invite is owed while its answer can still count.** That is:
  - an `Invite(EmbargoEvent)` to the participant whose consent row is still `INVITED`, for a proposal that is still open and whose RSVP deadline has not passed (EP-09-002, EP-09-011, CM-31-013);
  - the full-case Invite, until the participant replies to it (CM-11-010).
    It has no RSVP deadline yet; #5320 proposes one, and the resend stops at that deadline once it exists.
- **A resend is the activity as first sent.** It has the same id, `ledgerPosition` and RSVP deadline (SYNC-18-002).
  A receiver that already handled it treats it as a redelivery and does nothing (IE-10-001); a receiver that dropped it handles it as new.
  Resending never extends a deadline, so silence before the deadline is still a pocket veto.
- **Resends are rate-bounded per Invite and participant.** The CASE_MANAGER skips an Invite whose earlier send is still pending in its outbox, as replay does (SYNC-15-012).
  Each consecutive resend of one Invite to one participant doubles the cooldown before the next, up to a fixed ceiling, as replay does (SYNC-15-013).
- **A resend is not a case event.** The Invite's emission was ledgered when it was first sent, so the resend commits no ledger entry.
  It does not change the outcome of the activity that stated the position.
- **A participant states its position once its replica is seeded.** So the trigger fires even for a joiner that would otherwise stay silent.
- **The receiver's replay `Question` is removed.** The pre-bootstrap queue keeps its window and its warning on expiry (CBT-03-001, CBT-03-006), and recovery belongs to the CASE_MANAGER.

### Consequences

- Good, because a joiner whose Invite was dropped before its case copy receives it again as soon as it says where it stands, and can consent or judge the case.
- Good, because the same rule recovers an Invite lost for any other reason, such as a dead-lettered delivery, the next time its addressee states a position.
- Good, because the CASE_MANAGER keeps no timer and the receiver no longer depends on more traffic to expire its queue.
- Good, because resending the activity as first sent keeps the ledger, the RSVP deadline and the full-case Invite's ledger floor (CM-11-012) unchanged.
- Bad, because a participant that deliberately leaves an Invite unanswered is sent it again, up to the cooldown ceiling, until the deadline passes or, for the full-case Invite, indefinitely until #5320 lands.
- Bad, because a participant that never states its position is not reached; the post-seed statement makes this rare, not impossible.
- Bad, because the CASE_MANAGER must keep a cooldown record per Invite and participant.

## Validation

Tests drop a joiner's relayed `Invite(EmbargoEvent)` and full-case Invite from its expired pre-bootstrap queue, deliver the case copy, and assert that the joiner's post-seed `Read(CaseLedgerEntry)` brings both back with their original ids, so the joiner can accept the embargo before its RSVP deadline.
A participant that already answered, or whose proposal was decided, is sent nothing, and no resend commits a ledger entry.

## Pros and Cons of the Options

### The CASE_MANAGER resends owed Invites on a position statement

- Good, because a position statement tells the CASE_MANAGER the replica holds the case, which is the moment a resend can land.
- Good, because the position-statement answer path, its active-participant check and its rate bound exist.
- Good, because it recovers any lost Invite, not only one dropped before the case copy.
- Bad, because it needs per-Invite cooldown state on the CASE_MANAGER.

### Make the receiver's replay `Question` work

- Good, because the message is already sent.
- Bad, because the receiver sends it only when its queue expires, and expiry runs only when more traffic or the case copy arrives, so a quiet joiner may never send it.
- Bad, because it would need a new handler and semantic type for a message whose meaning, a request for a case copy, the case copy itself makes moot by the time the queue expires on its arrival.

### Accept the window as a bound

- Good, because it needs no code.
- Bad, because a joiner loses its chance to consent to delivery timing, which EP-09-011 exists to prevent.
- Bad, because a joiner whose full-case Invite was dropped cannot judge the case at all.

### Hold pre-bootstrap messages with no time limit

- Good, because nothing is dropped while the case copy is delayed.
- Bad, because a case copy that never arrives leaves messages the receiver cannot trust held for as long as the process runs (CBT-03-001).
- Bad, because an Invite lost in transport, rather than dropped from the queue, is still never resent.

## More Information

Generated spec requirements: none yet; the implementation issues that build this decision add them.
