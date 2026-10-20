---
status: proposed
date: 2026-10-16
created: 2026-10-16
updated: 2026-10-20
revision: 2
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0111, ADR-0119, ADR-0122, ADR-0124;
  specs/case-ledger-processing.yaml CLP-07-013, CLP-07-014;
  specs/case-management.yaml CM-23-016
informed: []
stakeholder_type: [project-contributor]
---

# One Atomic Commit per Embargo Act

## Context and Problem Statement

Every change the CASE_MANAGER makes to the case file is its own ledger entry, and the act's entry comes first (CLP-07-013, ADR-0124).
So one embargo act commits several entries: the act's own, then one `Create` or `Update(EmbargoConsent)` for each consent row it changes.
The CASE_MANAGER decides every row before the first commit.

The entries used to be committed one at a time, each in its own DataLayer write.
When a later commit failed, the entries already committed stayed committed, and their changes were saved.
The case was then in a state no single act produces.
A proposal could be in the register while some participant held no row for it, which every later read of that proposal refuses (ADR-0122).
A relayed Invite could be committed while the invitee's row was never moved to `INVITED`, so the invitee's answer was checked against the wrong starting state.

Nothing finished the act.
A repeated trigger starts a new act, and a redelivered received act is stopped by its idempotency guard.
One act, the stub re-issue, had its own repair pass that re-derived the row it owed; no other act had one.

The question this record settles: how does the CASE_MANAGER keep a failure part-way through an act from leaving the act half done?

## Decision Drivers

- An act's consequences succeed all at once or fail all at once; a failure never leaves half-done work for a later run to finish.
- An act's entries are decided once, before the first commit; nothing may decide them again later from a clock or policy that has moved on.
- A received act's own entry is committed by intake, before the act's tree decides its consequences (ADR-0111).
- Replicas receive entries one `Announce(CaseLedgerEntry)` at a time and apply them by copying (CM-23-016).
- This is a prototype: no recovery machinery for a state that atomicity can rule out.

## Considered Options

- **A — Store the planned entries before the first commit; the next CASE_MANAGER embargo run on the case finishes them.**
- **B — Re-derive the owed entries from the committed act, one repair pass per act, as the stub re-issue did.**
- **C — Commit the act and its consequences in one DataLayer transaction.**
- **D — Leave the state and make readers tolerate a missing or unmoved row.**

## Decision Outcome

Chosen option: **C, one DataLayer transaction per act**.

The DataLayer port offers a transaction: every write inside the block commits together, or none of them does, and every read inside it sees its own writes.
The CASE_MANAGER's embargo commit step opens one transaction for the act.
Inside it, the step trial-applies every planned entry to a copy of the case file, so a step that will not apply refuses the act before anything is written.
It then commits each entry in order, with the activity, outbox rows and announcements each commit writes, and saves the case-file changes the entries carry.
A failure at any point rolls all of it back: no entry, no queued activity and no row change is kept.
The step takes a list of entries, so several acts that must land together, such as a rejection followed by the termination it causes, go through the same call.

The ledger and the sync shape do not change.
Each entry is still its own `CaseLedgerEntry` and its own announcement, so a replica copies them one at a time, as before.

The stub re-issue's repair passes are removed.
Its replacement Invite is built, queued and committed in the same transaction as the invitee's row, so a failure leaves the stub stale and the next run re-issues it from the start.

### Known atomicity requirement: a received act's own entry

For a received act, intake commits the act's own entry first, in its own transaction, before the tree decides the consequences (ADR-0111).
The consequences then commit as one transaction after it.
So a failure in the consequences leaves the received act's entry committed without them.
Closing this gap moves the received act's own entry into the same transaction as its consequences, which needs a revision of ADR-0111 (#4933).

### Known atomicity requirement: consequences committed by later nodes

Some consequences of an act are committed by later nodes in the act's tree, each in its own transaction, after the act's transaction has committed.
The stub re-issue is one: an act that changes the embargo in force makes every outstanding stub Invite stale (CM-11-016), and each replacement commits on its own.
The relay of a proposal is another: each relayed Invite, with its invitee's row, commits on its own after the proposal (EP-09-002).
So a failure in a later node leaves the act committed and that consequence missing.
Nothing is half-written, because each later commit is atomic, but the consequence waits for a later run, or for a redelivery that relays again.
Closing this gap commits the act and these consequences in one transaction (#4934).

### Why revision 1 was replaced

Revision 1 chose option A: a stored plan of the owed entries, and a finishing node that ran first in every CASE_MANAGER embargo tree for the case.
The maintainer rejected it: a half-done act should not exist at all, and a stored plan, a finishing node and a deferred finish are recovery machinery for a state an atomic commit rules out.
Revision 1 rejected option C because a received act's entry is committed by intake before its consequences, and because it read C as a single ledger append that needs a new ledger and sync shape.
Revision 2 takes C as a storage transaction instead, which leaves the ledger and sync shape alone, and names the intake ordering as the known gap rather than a reason to keep half-done acts.

Option A was rejected: it keeps a half-done act visible on every node until a later run finishes it, and it adds a bookkeeping record and a finishing node to every embargo tree.
Option B was rejected: each act needs its own re-derivation, and a re-derivation can decide a different row than the first run did once the clock or local policy has changed, such as an RSVP deadline.
Option D was rejected: every register entry has a row on every participant (ADR-0122), and an unmoved row misjudges a later answer.

### Consequences

- Good, because a failed commit in the middle of an act leaves the case as it was before the act.
- Good, because no act needs a repair pass, and no run finishes another run's work.
- Good, because the ledger, the entry ids and the sync shape are unchanged.
- Bad, because a transaction holds the store's write lock for the whole act, so another writer on the same store waits for it.
- Bad, because a received act's own entry still commits before its consequences, until ADR-0111 is revised.
- Bad, because consequences that later nodes commit, such as the stub re-issue and the relay of a proposal, still commit after the act.

## Validation

- A test fails an act's second commit and asserts that the CASE_MANAGER holds no entry, no queued activity and no row change from the act.
- A test fails the case-file save after every commit and asserts that no entry is kept.
- A test commits a two-entry act and asserts that a replica copying its announcements holds the same rows as the CASE_MANAGER.
- Adapter tests assert that a transaction commits every write together, rolls every write back when it raises, rolls back only its own writes when nested, and wakes the outbox monitor only after it commits (DL-02-004).
- Two strict-xfail tests record the known atomicity requirements, one per gap (#4933, #4934).

## More Information

- ADR-0111 — intake is the first received-side stage.
- ADR-0122 — per-embargo participant consent and the embargo register.
- ADR-0124 — every change to the case file is an entry, and replicas copy.
- #4764 — the concern this record answers.
- #4855 — the implementation, whose acceptance criteria the maintainer reworded for revision 2.

Generated spec requirements: `case-ledger-processing.yaml` CLP-07-015.
