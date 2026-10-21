---
status: accepted-provisional
date: 2026-10-16
created: 2026-10-16
updated: 2026-10-21
revision: 5
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0111, ADR-0119, ADR-0122, ADR-0124;
  specs/case-ledger-processing.yaml CLP-07-013, CLP-07-014;
  specs/case-management.yaml CM-23-016
informed: []
stakeholder_type: [project-contributor]
---

# One Atomic Commit per CASE_MANAGER Act

## Context and Problem Statement

Every change the CASE_MANAGER makes to the case file is its own ledger entry, and the act's entry comes first (CLP-07-013, ADR-0124).
So one act commits several entries.
An embargo act commits its own entry, then one `Create` or `Update(EmbargoConsent)` for each consent row it changes.
A received `Leave(VulnerabilityCase)` commits its `close_case` entry, then one status entry for each RM transition it causes (CM-23-001).
The CASE_MANAGER decides every row before the first commit.

The entries used to be committed one at a time, each in its own DataLayer write.
When a later commit failed, the entries already committed stayed committed, and their changes were saved.
The case was then in a state no single act produces.
A proposal could be in the register while some participant held no row for it, which every later read of that proposal refuses (ADR-0122).
A relayed Invite could be committed while the invitee's row was never moved to `INVITED`, so the invitee's answer was checked against the wrong starting state.

Nothing finished the act.
A repeated trigger starts a new act, and a redelivered received act is stopped by its idempotency guard.
One act, the stub re-issue, had its own repair pass that re-derived the row it owed; no other act had one.

The question this record settles: how does the CASE_MANAGER keep a failure part-way through any act from leaving the act half done?

## Decision Drivers

- An act's consequences succeed all at once or fail all at once; a failure never leaves half-done work for a later run to finish.
- An act's entries are decided once, before the first commit; nothing may decide them again later from a clock or policy that has moved on.
- A received act's own entry is committed by the guarded commit after intake and the guards, before the act's tree commits its consequences (ADR-0111).
- Replicas receive entries one `Announce(CaseLedgerEntry)` at a time and apply them by copying (CM-23-016).
- This is a prototype: no recovery machinery for a state that atomicity can rule out.

## Considered Options

- **A — Store the planned entries before the first commit; the next CASE_MANAGER embargo run on the case finishes them.**
- **B — Re-derive the owed entries from the committed act, one repair pass per act, as the stub re-issue did.**
- **C — Commit the act and its consequences in one DataLayer transaction.**
- **D — Leave the state and make readers tolerate a missing or unmoved row.**

## Decision Outcome

Chosen option: **C, one DataLayer transaction per act**, for every act the CASE_MANAGER commits, not only embargo acts.

The DataLayer port offers a transaction: every write inside the block commits together, or none of them does, and every read inside it sees its own writes.
The CASE_MANAGER's embargo commit step opens one transaction for the act.
Inside it, the step trial-applies every planned entry to a copy of the case file, so a step that will not apply refuses the act before anything is written.
It then commits each entry in order, with the activity, outbox rows and announcements each commit writes, and saves the case-file changes the entries carry.
A failure at any point rolls all of it back: no entry, no queued activity and no row change is kept.
The step takes a list of entries, so several acts that must land together, such as a rejection followed by the termination it causes, go through the same call.

Some consequences of an act are committed by later nodes in the act's tree.
The stub re-issue is one: an act that changes the embargo in force makes every outstanding stub Invite stale (CM-11-016).
The relay of a proposal is another: each relayed Invite commits with its invitee's row (EP-09-002).
The tree runs the act's commit step and those later nodes inside the same transaction, as one composite node (`ActTransaction`).
The commit step's own transaction is then part of the act's transaction, so a failure in any later node also rolls back the act.
Each CASE_MANAGER arm of an embargo trigger tree is one such node.
So is every received tree's commit of the act's own entry together with the effects after it (ADR-0151): the received-tree factory gives every tree that commits to a case this shape by default.
A tree runs outside it only by naming a registered, reasoned exemption, and none is registered.
A tree that includes another act's tree, such as a rejection that ends the embargo, nests one `ActTransaction` inside another, and the inner one is part of the outer one.

The ledger and the sync shape do not change.
Each entry is still its own `CaseLedgerEntry` and its own announcement, so a replica copies them one at a time, as before.

The stub re-issue's repair passes are removed.
Its replacement Invite is built, queued and committed in the act's transaction with the invitee's row, so a failure keeps neither the act nor the replacement, and no later run has anything to finish.

### A received act's own entry

For a received act, the guarded commit of the act's own entry runs after intake and the guards, and before the consequences (ADR-0111).
That commit runs in the same transaction as the consequences, so a failure in any of them keeps neither the entry nor any consequence (ADR-0151).
A later delivery of a failed received act is then not stopped as a repeat, and runs the act again.
Revision 3 named this as a known gap: the entry was committed in its own transaction first, the change it carried was applied again after the rollback, and a received proposal whose relay failed stayed in the register with no rows, its redelivery refused.
Revision 4 closes it (#4933).

### What revision 5 changed

Revisions 1 to 4 decided the rule for embargo acts, and the received-tree factory took the one-act shape as an opt-in that only embargo trees used.
Case trees kept committing their consequences after the act.
A received `Leave` could keep its `close_case` entry while the status entries it caused were missing, a joiner's relay or a reinstated participant's embargo Invite could fail after the join or reinstatement was kept, and recovery code finished such acts on a later delivery.
Revision 5 applies the rule to every act the CASE_MANAGER commits.
One act is the factory's default, so a new tree cannot drop it silently, and the recovery code that finished a half-done case act is removed (#4983).

### Why revision 1 was replaced

Revision 1 chose option A: a stored plan of the owed entries, and a finishing node that ran first in every CASE_MANAGER embargo tree for the case.
The maintainer rejected it: a half-done act should not exist at all, and a stored plan, a finishing node and a deferred finish are recovery machinery for a state an atomic commit rules out.
Revision 1 rejected option C because a received act's entry is committed by intake before its consequences, and because it read C as a single ledger append that needs a new ledger and sync shape.
Revision 2 takes C as a storage transaction instead, which leaves the ledger and sync shape alone, and names the intake ordering as the known gap rather than a reason to keep half-done acts.

### What revision 3 changed

Revision 2 committed the consequences that later nodes commit, the stub re-issue and the relay of a proposal, each in its own transaction after the act's, and named that as a second known gap.
When one of them failed, the act stayed committed and the consequence was missing; for the CASE_MANAGER's own proposal, nothing relayed it again.
Revision 3 closes that gap: the act's commit step and those later nodes run in one transaction (#4949).

Option A was rejected: it keeps a half-done act visible on every node until a later run finishes it, and it adds a bookkeeping record and a finishing node to every embargo tree.
Option B was rejected: each act needs its own re-derivation, and a re-derivation can decide a different row than the first run did once the clock or local policy has changed, such as an RSVP deadline.
Option D was rejected: every register entry has a row on every participant (ADR-0122), and an unmoved row misjudges a later answer.

### Consequences

- Good, because a failed commit in the middle of an act leaves the case as it was before the act.
- Good, because no act needs a repair pass, and no run finishes another run's work.
- Good, because a received tree gets the one-act shape without asking for it, so a new tree cannot leave its consequences outside its act.
- Good, because the ledger, the entry ids and the sync shape are unchanged.
- Bad, because a transaction holds the store's write lock for the whole act, including its later nodes, so another writer on the same store waits for it.
- Bad, because an effect that fails as an expected outcome, such as a withheld status adoption, must not return `FAILURE`, or the act loses its own entry.

## Validation

- A test fails an act's second commit and asserts that the CASE_MANAGER holds no entry, no queued activity and no row change from the act.
- A test fails the case-file save after every commit and asserts that no entry is kept.
- A test commits a two-entry act and asserts that a replica copying its announcements holds the same rows as the CASE_MANAGER.
- Adapter tests assert that a transaction commits every write together, rolls every write back when it raises, rolls back only its own writes when nested, and wakes the outbox monitor only after it commits (DL-02-004).
- Tests fail the stub re-issue after a termination and after an accept, and the relay after the CASE_MANAGER's own proposal and after a received one.
  Each asserts that the act keeps no consent row change, no re-issued or relayed Invite and no queued activity, and that a trigger act keeps no entry (#4949).
- Tests fail a received withdrawal's row commit and a received proposal's relay, and assert the received act keeps no entry, and that a redelivery of the proposal is applied (#4933).
- Tests fail the relay to a joiner and a reinstated participant's embargo Invite, and assert the act keeps no joined mark, consent row, outbox entry or ledger entry, and that a redelivery is processed afresh.
  Tests fail a step of a Leave's closure and assert no `close_case` entry is kept (#4983).
- An architecture test asserts that every received tree that commits runs its own entry and every node after it in one `ActTransaction`, or names a registered exemption, held to equality with a pinned set in both directions (#4983).

## More Information

- ADR-0111 — intake is the first received-side stage.
- ADR-0122 — per-embargo participant consent and the embargo register.
- ADR-0124 — every change to the case file is an entry, and replicas copy.
- #4764 — the concern this record answers.
- #4855 — the implementation, whose acceptance criteria the maintainer reworded for revision 2.
- #4949 — revision 3: one transaction for the act and the consequences its later nodes commit.
- #4933 — revision 4: a received act's own entry commits in that transaction too (ADR-0151).
- ADR-0151 — a received act commits its own entry with its consequences.
- #4983 — revision 5: one act for every CASE_MANAGER act, as the received-tree factory's default.

Generated spec requirements: `case-ledger-processing.yaml` CLP-07-015, `datalayer.yaml` DL-02-004.
