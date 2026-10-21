---
status: proposed
date: 2026-10-21
created: 2026-10-21
updated: 2026-10-21
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0068, ADR-0111, ADR-0135, ADR-0149, ADR-0153;
  specs/case-ledger-processing.yaml CLP-10-010, CLP-10-017, CLP-10-018,
  CLP-10-019; specs/handler-protocol.yaml HP-01-003, HP-01-005, HP-10-001;
  specs/case-management.yaml CM-15-002; issues #5011, #3742, #4943, #5019
informed: []
partially_supersedes:
  - 0111-intake-is-the-first-received-side-stage.md
  - 0135-compose-received-trees-never-chain-them.md
stakeholder_type: [project-contributor]
---

# A Received Message Is One Staged Record, Archived Only When Applied

## Context and Problem Statement

Intake is the first stage of every received tree (ADR-0111).
It archives each arrival as received before any door guard runs, and a refusal must leave that archive in place (CLP-10-018).
ADR-0111 accepted the cost: storage grows with traffic the receiver declines.

That cost is larger than storage.
A message that is not for the receiver, and that it will never act on, is kept permanently in full.
The doors that would have ruled it out run after the write, so an early answer cannot spare the later work.
A message waiting for its case is held in a separate record, `DeferredInboxActivity`, with its own lifecycle, and a duplicate is detected at ingress and then run through the whole tree again to be answered by each handler's idempotency.
The handler's own in-memory intake state (`found_ids`, `stored_anything`) is what tells a later stage whether this delivery was new.

ADR-0153 asks the role question once, as a door stage.
With every door stage now a cheap read, the order of the questions can let an early answer end the run before anything is stored.

Where should a received message rest while it is judged, and what should the receiver keep once it has been judged?

## Decision Drivers

- Receipt is a fact: the receiver must be able to say it received a message, from whom, when, and why it declined it (the reason ADR-0111 put intake first).
- HP-01-005 and HP-10-001: a misaddressed copy, including a `cc`-only copy of an `Offer(Report)`, is refused and discarded; it is not the receiver's record.
- HP-01-003: a duplicate is `SKIPPED`, a refusal is `REFUSED`, a deferral is `DEFERRED`.
- ADR-0149: the archive is the received body as the parser sealed it, and a held message is its sealed body too.
- ADR-0135: the handling tree is one unit with one blackboard.
- A crash mid-run must not lose a message, nor apply it twice.

## Considered Options

1. **One staged record per message; archive on applied, receipt stub on refused.**
2. **Keep intake first, and prune refused archives later.** Archive every arrival as today, and have a sweep reduce refused ones to a summary.
3. **Keep intake first, unchanged.** Accept the storage and keep the separate holding record.

## Decision Outcome

Chosen option: **"One staged record per message"**, because it is the only option under which an early answer prevents the later work and the write, receipt stays a fact, and waiting, duplicates and crash recovery share one mechanism.

### Decision details

1. **The order of questions.** Each answer can end the run:
   1. Addressed to me? No → `REFUSED` (HP-01-005).
   2. Seen before? Yes → the outcome recorded for it (detail 5).
   3. Which path, and does this message type declare a branch for it (ADR-0153)? No → `REFUSED`. No case yet → wait for the case, or take the no-case branch.
   4. Is the case open to external writes, and is the sender entitled (CM-23-013, HP-01-006)?
   5. The handling tree: clock decisions, precondition guards, commit, effects (CLP-10-010, CLP-10-025).

   This replaces the stage order of ADR-0135 detail 3, which began with intake.
   The post-close boundary moves from ahead of the addressee check to beside the sender guard, because whether a closed case takes the write is a question about the case, asked once the message is known to be for the receiver.
2. **One record per message, with a stage field.**
   The record moves `received → door-checked → [waiting] → handled → final outcome`.
   Each stage has one way in and two ways out: move on, or leave with an outcome.
   The record holds the sealed received body (ADR-0149) while it is in holding.
   It rests only where time can pass: waiting for its case, which absorbs `DeferredInboxActivity`, or waiting for a local decision.
3. **A message leaves holding only on its final outcome.**
   - Applied → the long-term archive, the `ReceivedActivityRecord` that holds the sealed body (CLP-10-017, ADR-0149).
   - Refused → a **receipt stub**: the sender, the message id, the time of receipt, the refusal reason and a hash of the received body. The body itself is not kept.
   - Duplicate of an applied message → dropped, because the original is already archived.

   This replaces ADR-0111 details 3 and 4: intake no longer archives every arrival, and a refusal leaves a receipt stub, not the archive.
4. **A crash leaves the message in holding.**
   Because the record leaves holding only on its final outcome, a crash mid-run leaves it to be run again.
   Every handling tree must tolerate that re-run.
   The once-per-act commit and derived-id sends (SYNC-09-002, OX-06-002) are meant to provide this; it must be verified for every tree, not assumed.
5. **A resend is answered from what was recorded.**
   A resend whose body hash matches a receipt stub is `REFUSED` again with the stub's reason, and nothing is re-run: a refusal is whole and final for that activity, and a sender that wants another outcome sends a new activity.
   A resend whose hash differs from what the receiver holds, archive or stub, is refused as a reused id (IE-10-002, #5019).
   A resend of an applied message is `SKIPPED`.
   No refusal notice is sent again for a resend.
6. **`Offer(Report)` takes the ordinary order.**
   An addressed `Offer(Report)` takes the no-case branch, which stores the report and the Offer and then asks whether to create a case.
   Declining to create one is still an applied outcome, so the message is archived and CM-15-002 holds.
   A `cc`-only copy is refused at the addressee door and leaves a stub (HP-10-001).
   The `OFFER_REPORT_STORED_FIRST` addressee exemption retires.
7. **Readers in the run read the holding record; readers after it read the archive.**
   A node that embeds or reads the body of the message being handled, such as the refusal notice and the late-accept acknowledgement, reads it from the holding record.
   A reader after the run reads the archive, which now holds only applied messages, or the stub, which says only that a message was refused and why.
   What tells a stage that a delivery is new is the record's stage and the seen-before answer, not in-memory state from an earlier stage.
8. **Split points are around the handling tree only.**
   The stage boundaries are arrival, doors, waiting, the handling tree and the outcome.
   A stage reads only the record and the store, never what an earlier stage left in memory.
   The handling tree stays one unit with its blackboard (ADR-0135).
   This adds no queues or workers; the rule keeps the option of running the stages as separate queues or functions later.

### Consequences

- Good, because a message that is not for the receiver costs one read and one stub, not a permanent copy.
- Good, because waiting for a case, duplicate detection and crash recovery share the one record instead of three mechanisms.
- Good, because receipt is still a fact for every message: the stub records who sent what, when, and why it was declined, and its hash lets a reused id be detected without the body.
- Good, because `Offer(Report)` no longer needs a registered exemption, and a `cc`-only copy gets the discard HP-10-001 asks for.
- Bad, because the receiver no longer keeps the body of a refused message, so evidence of what a misbehaving sender sent is only in the process log.
- Bad, because every handling tree must be shown to tolerate a re-run after a crash, which today nothing checks.
- Bad, because it amends CLP-10-010, CLP-10-017, CLP-10-018 and CLP-10-019, the intake-first ratchets and the deferral queue's storage, which is a persistence change.

### Confirmation

- An architecture test fails when a stage outside the handling tree reads in-memory state written by an earlier stage.
- Tests drive each final outcome and assert what remains: the archive for applied, a stub with no body for refused, nothing new for a duplicate.
- Tests drive a resend against a stub with a matching hash, a stub with a different hash, and an archive, and assert the verdict detail 5 gives each.
- A per-tree re-run test drives each handling tree twice from holding and asserts that nothing is committed or sent twice.

## Pros and Cons of the Options

### One staged record per message

- Good, because the order of questions does the work: an early answer ends the run before anything is stored.
- Good, because one record replaces the holding record, the duplicate re-run and the in-memory intake flags.
- Bad, because it changes the intake stage of every tree and the stored shape of a refused message.

### Keep intake first, and prune refused archives later

- Good, because the trees keep their shape.
- Bad, because the full body is stored and then removed, which CLP-10-018 forbids and a crash between the two leaves half-done.
- Bad, because the doors still run after the write, so nothing is spared.

### Keep intake first, unchanged

- Good, because nothing moves.
- Bad, because the receiver keeps, permanently, the content of every message it declined, including copies that were never addressed to it.
- Bad, because waiting, duplicates and recovery remain three mechanisms.

## More Information

- Source: #5011. It builds on ADR-0153, which adds the path door stage this record orders.
- It partially supersedes ADR-0111 (details 3 and 4) and ADR-0135 (detail 3, the stage order).
- Related: ADR-0149 (the archive is the sealed received body), #3742 (persist evidence for deferred replay), #5019 (refuse a reused id with a different body), #5033 (what a `cc` on a report could mean).
