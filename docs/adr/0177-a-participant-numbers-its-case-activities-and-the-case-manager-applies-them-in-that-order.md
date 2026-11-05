---
status: proposed
status_override: >-
  Decided by the maintainer in planning (#5202, #5203). The SYNC-21 tests are
  strict xfails written before the counter is built, so they verify no built
  behaviour; SYNC-21-005 holds only because an entry keeps the received body.
  The record stays proposed until the counter is built and its open questions
  are decided.
date: 2026-11-05
created: 2026-11-05
updated: 2026-11-05
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0037, ADR-0079, ADR-0154, ADR-0156, ADR-0161, ADR-0164;
  specs/sync-ledger-replication.yaml SYNC-11, SYNC-14, SYNC-18, SYNC-19;
  specs/case-ledger-processing.yaml CLP-02-005, CLP-05-001, CLP-05-006,
  CLP-05-008, CLP-07-011; specs/idempotency.yaml ID-02-001;
  issues #5202, #5203, #5396
informed: []
stakeholder_type: [project-contributor]
---

# A Participant Numbers Its Case Activities, and the Case Manager Applies Each Sender's in That Order

## Context and Problem Statement

A participant sends its case activities to the CASE_MANAGER, which judges each one and commits the admitted ones to the case ledger.
The transport promises no delivery order ([ADR-0037](0037-buffer-out-of-order-ledger-entries.md)), and per-recipient delivery order is not a protocol guarantee (SYNC-19-003, [ADR-0161](0161-eventual-consistency-is-the-protocols-ordering-guarantee.md)).
So two activities one participant sends can reach the CASE_MANAGER in either order.

Nothing on the wire tells the CASE_MANAGER which of them was sent first.
Each activity carries its sender's ledger tail as `ledgerPosition` (SYNC-18-001, [ADR-0156](0156-every-case-activity-states-its-senders-ledger-position.md)), but two activities sent before the first is committed carry the same tail.
ActivityStreams 2.0 and ActivityPub have no sequencing of their own.

The arrival-order audit (#5102) found two decisions that this leaves to arrival order, which SYNC-19-001 forbids:

- A participant sends `Accept` and then `Reject` of one relayed `Invite(EmbargoEvent)` before the first is committed.
  The CASE_MANAGER records a changed answer (CM-13-005, CM-18-003), so the answer that arrives last decides the participant's consent (#5202).
- A participant sends `Add(Note)` and then `Leave(VulnerabilityCase)`.
  If the Leave arrives first, the sender is no longer active when the note arrives, and the sender guard refuses the note with no notice (HP-01-006, CLP-02-005), so the note is lost silently (#5203).

How does the CASE_MANAGER learn the order in which one participant sent its activities, and what does it do when they arrive in another order?

## Decision Drivers

- The case ledger records what the participant meant: its later act decides after its earlier one, whatever the network did.
- A lost activity does not stop the sender's later activities forever.
- Nothing is lost silently: when the CASE_MANAGER refuses an activity because of its place in the order, the sender is told.
- Protection against a forged or replayed activity comes from one place, the activity's signature ([ADR-0164](0164-actors-sign-content-with-object-level-proofs-from-seeded-keys.md)), not from each mechanism separately.
- Correctness does not depend on every sender behaving well.
- The fix lives in the protocol, so a second implementation gets the same order.

## Considered Options

- A per-(sender, case) counter on each activity, applied in counter order with a bounded hold.
- A hash link from each activity to its sender's previous activity.
- A sender-side hold: a participant sends no assertion that could conflict with a pending one until that one is applied.
- A counter that starts at a random value, as TCP's initial sequence number does.

## Decision Outcome

Chosen option: "A per-(sender, case) counter on each activity, applied in counter order with a bounded hold", because it gives the CASE_MANAGER the sender's order with one small number, survives a lost activity without deadlock, and tells the sender about every activity it refuses for its place in the order.

### The sender numbers its activities

- Each participant numbers the case activities it sends to the CASE_MANAGER with a counter kept per (sender, case).
  The first is 1, and each next one is one more than the last.
- The number travels as the activity's `senderSequence`, a Vultron extension property beside `ledgerPosition`.
  It is not a change to the ActivityStreams vocabulary, and in this codebase only `vultron.wire.as2.factories` produces it, as it does `ledgerPosition` (SYNC-18-008).
- A resent activity keeps its number, as it keeps its position (SYNC-18-009): a resend delivers the sealed body (OX-07-001).
- An admitted activity's number stays in its ledger entry, because the entry keeps the body as received (CLP-07-011), as it keeps the position (SYNC-18-006).

### The CASE_MANAGER judges each sender's activities in number order

"Judge" here means the received processing that admits or refuses the activity on its merits, as today.

- For each (sender, case) the CASE_MANAGER keeps a next expected number: one more than the highest number from that sender it has judged or skipped, and 1 before any.
- An activity whose number is the next expected one is judged on arrival.
- An activity whose number is higher waits in a hold, as the body that arrived, until the missing numbers arrive.
  When they do, the CASE_MANAGER judges them and then the held activities, in number order.
- The hold is bounded.
  It ends when its wait expires, whether or not anything else arrives, or when the sender's held activities reach a small cap.
- **Fast-forward.**
  When a hold ends with numbers still missing, the CASE_MANAGER skips them, judges what it holds in number order, and moves the next expected number past the highest one it judged.
  So a lost activity delays its sender's later activities for at most the wait, and never blocks them.
- The CASE_MANAGER never refuses an activity for its number, except the late case below.

### A late number is refused with a notice

- An activity whose number is below the next expected one arrived after its gap was skipped, or comes from a sender that lost its counter.
  The CASE_MANAGER refuses it and writes nothing.
- It sends the sender a refusal notice (CLP-05-001) that names the next expected number as `expectedSenderSequence`.
  So the refusal is never silent.
- The sender may assert the content again as a new activity, with a new id and a fresh number.

### A sender that lost its counter resumes

- A sender that lost its record of the last number it used, through data loss or a rebuild, resumes from the highest of its own numbers in the case ledger it holds.
  Its admitted activities keep their numbers in their ledger entries.
- A sender that receives the refusal notice resumes at or above the number the notice names.

### Stored state

The maintainer approved this persistence change.

- A participant keeps the last number it used, per case.
- The CASE_MANAGER keeps, per (sender, case), its next expected number and the activities it holds.
- Both live in the actor's DataLayer, so the order survives a restart.

### Security

The counter is predictable, and that is acceptable.
Forgery is prevented by the object-level signature of ADR-0164, which covers the whole activity body, the number included.
Until signing is built, anyone can already forge any activity, so a predictable number adds no new weakness.
The bounded wait and the cap limit what a forged high number can do: it delays one sender's own activities for at most one wait.

### Choices the maintainer left open

The maintainer left the points below open.
Each states this record's recommendation, labelled as such, and the specification adopts it.

- **Which activities carry the number.**
  *Recommendation:* every activity a participant sends to the CASE_MANAGER that carries a `ledgerPosition` (SYNC-18-001), except `Read(CaseLedgerEntry)` and `Reject(CaseLedgerEntry)`.
  The SYNC-18-017 exclusions follow from the first clause: an activity sent before its sender holds the ledger, one whose object states its own position, and a `Create(ProcessingFault)` carry no position and so no number.
  The two ledger requests are excluded because they are about the ledger itself, not case events (CLP-02-013), and a lost activity is often the reason for one: holding a request for a missed entry behind the gap it reports would delay the repair.
  The CASE_MANAGER's own activities carry no number.
  Its case events are ordered by the ledger itself (CLP-14-001), and its messages outside the ledger are governed by SYNC-19-004.
- **An activity with no number.**
  *Recommendation:* the CASE_MANAGER judges it when it arrives, as it judges every activity today, and neither holds it nor refuses it for the missing number.
  This is the robustness principle: a sender that does not number gets today's behaviour and today's arrival-order risk, and a sender that numbers is protected.
  It differs from `ledgerPosition`, whose absence is refused (SYNC-18-015), because the position is evidence the ledger keeps for every act, while the number protects only its own sender's order.
- **Default wait and cap.**
  *Recommendation:* a wait of 120 seconds and a cap of 16 held activities per sender and case, both configurable.
  The wait covers one delivery attempt that times out (30 seconds by default) and the retries after it (backoff up to 30 seconds), which is when a reordered activity is still on its way.
  It is shorter than the default pending-assertion timeout of 180 seconds (SYNC-11-005), so a hold has ended, and the sender has had any notice, before the sender gives up on the activity.
  The cap bounds the storage one sender can take, and one sender seldom has 16 activities in flight to one case.
- **Repeats and idempotency.**
  *Recommendation:* the CASE_MANAGER finds a repeat by id (ID-02-001) before it compares the number.
  A repeat of an activity it already judged changes nothing and gets no notice (CLP-05-006).
  A repeat of an activity it holds changes nothing, and the one held copy stays.
  An activity with a new id whose number equals that of a held activity is refused with the same notice as a late one: one sender cannot mean two activities by one number, and the first to arrive keeps its place.
- **The arrival-order rule (SYNC-19-001).**
  *Recommendation:* the counter is how the CASE_MANAGER meets SYNC-19-001's clause about two assertions one sender sent before the first was committed.
  Within the wait, the CASE_MANAGER judges them in send order whatever order they arrive in, so the ledger records the sender's order and every replica learns it.
  An activity delayed past the wait is treated as lost.
  Its fate then depends on timing, but the outcome is still one ledger entry or one notice, and the sender is told.
  SYNC-19-002 still holds, because replicas follow the ledger.
- **Resending refused content.**
  *Recommendation:* asserting the content again is a new act of the sender, never an automatic resend on the notice, which CLP-05-008 forbids.
  An automatic resend could undo the sender's later intent: a skipped `Accept` sent again after a later `Reject` was judged would reverse the participant's final answer.
- **Where the hold sits.**
  *Recommendation:* the hold runs at the CASE_MANAGER's inbox, after the parse edge and the repeat check and before the activity's received tree, so the tree judges each activity unchanged and in order.
  A held activity is kept as the body that arrived (VM-08-002), so its eventual ledger entry is that body (CLP-07-011).
  When it is released it is judged as a delivery of its own, as a held ledger entry is replayed (SYNC-14-009).
- **How #5202 and #5203 resolve.**
  In #5202, the `Accept` carries number *n* and the `Reject` *n + 1*.
  In either arrival order the CASE_MANAGER judges the `Accept` and then the `Reject`, so the consent row ends `DECLINED`: the answer sent last decides.
  In #5203, the `Add(Note)` carries *n* and the `Leave(VulnerabilityCase)` *n + 1*.
  If the Leave arrives first, it is held, so the note is judged while its sender is still active and is kept, and then the Leave is judged.
  The same holds for an assertion followed by its sender's `Leave(EmbargoEvent)`.
  Neither case needs a sender-side gate, so the pending-assertion check (SYNC-11) is unchanged.

### Consequences

- Good, because one sender's activities are judged in the order it sent them, which removes the two known arrival-order failures and the class they belong to.
- Good, because a lost activity costs at most one wait, never a deadlock.
- Good, because every activity refused for its number gets a notice naming the number to resume from.
- Good, because the counter needs no state beyond a number per case at the sender and a number plus a small hold per sender at the CASE_MANAGER.
- Good, because the ledger keeps each admitted activity's number, so a sender can recover its counter from the ledger it already holds.
- Bad, because every numbered case activity gains a field, and the CASE_MANAGER keeps new stored state per sender.
- Bad, because an activity delayed past the wait is refused even though it was sent in time; the sender must decide whether to assert it again.
- Bad, because a gap delays the sender's later activities by up to the wait.
- Neutral, because a sender that does not number keeps today's arrival-order behaviour.

### Open questions

- **A new CASE_MANAGER.**
  When the CASE_MANAGER role moves to another actor, the new one holds no next expected numbers, so it expects 1 from every sender.
  A sender already past 1 is then held for one wait before the fast-forward lets it through.
  The new CASE_MANAGER could instead start from the highest number of each sender in its ledger.
  This record does not decide that; the specification uses the simpler rule until the maintainer chooses.
- **Requiring the number.**
  Once every sender numbers, the CASE_MANAGER could refuse an activity with no number, as it refuses one with no position.
  This record keeps the robustness principle for now.

## Validation

The SYNC-21 requirements in `specs/sync-ledger-replication.yaml` implement this record.
Until the counter is built, each protocol requirement is marked by a strict `xfail` test in `test/core/use_cases/received/test_sender_sequence.py`, which fails loudly once the behaviour lands.
The one exception is SYNC-21-005, which already holds: a ledger entry keeps the body as received, so it keeps a number the body carries.
The two arrival-order tests in `test/core/use_cases/received/test_arrival_order.py` that reproduce #5202 and #5203 are reworked to the decided outcomes when the counter is built.

## Pros and Cons of the Options

### Per-(sender, case) counter with a bounded hold

- Good, because one integer per activity gives the full send order.
- Good, because the fast-forward bounds the cost of a lost activity.
- Good, because the sender recovers its counter from the ledger it holds.
- Bad, because the CASE_MANAGER keeps a hold and a timer per sender.

### Hash link to the sender's previous activity

Each activity would name the hash of its sender's previous one, as each ledger entry names its predecessor.

- Good, because it mirrors the ledger's hash chain.
- Good, because, while activities are unsigned, a link is harder to forge than a number.
- Bad, because both ends keep and follow more state: the sender keeps the previous body's hash, and the CASE_MANAGER must find a held activity by the hash it names rather than by a number.
- Bad, because a gap does not say how many activities are missing, and a sender that lost its state cannot rebuild the link from a number.
- Bad, because its one advantage disappears once activities are signed (ADR-0164).

### Sender-side hold until the earlier assertion is applied

A participant would not send a second assertion that could conflict with a pending one until the first one's ledger entry comes back.

- Good, because the CASE_MANAGER changes nothing.
- Bad, because correctness depends on every sender behaving well, including other implementations.
- Bad, because it is the weakest option, and the maintainer took it off the table.

### Random initial counter value

- Good, because an off-path attacker cannot guess the next number.
- Bad, because it defends only an unauthenticated channel; with signed activities it adds nothing.
- Bad, because a sender that lost its state cannot resume from a known start.

## More Information

The problem was found by the arrival-order audit (#5102) and filed as #5202 and #5203, under the Epic #5396.
The reproductions are the strict `xfail` tests `test_same_sender_answers_record_one_consent_in_either_order` and `test_note_sent_before_leave_is_kept_in_either_order` in `test/core/use_cases/received/test_arrival_order.py`.

Generated spec requirements: `sync-ledger-replication.yaml` SYNC-21.
