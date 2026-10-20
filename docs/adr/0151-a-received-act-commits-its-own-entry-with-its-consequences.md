---
status: proposed
date: 2026-10-20
created: 2026-10-20
updated: 2026-10-20
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0111, ADR-0135, ADR-0146;
  specs/case-ledger-processing.yaml CLP-07-013, CLP-07-015, CLP-10-006;
  issue #4933
informed: []
partially_supersedes:
  - 0111-intake-is-the-first-received-side-stage.md
stakeholder_type: [project-contributor]
---

# A Received Act Commits Its Own Entry with Its Consequences

## Context and Problem Statement

A received-side tree runs its stages in a fixed order: intake, the door guards, the clock decisions, the precondition guards, the guarded commit of the received activity's own entry, then the protocol effects (ADR-0111, ADR-0135, CLP-10-006).
ADR-0111 made the guarded commit a stage of its own, before the effects.
The factory composed each stage as its own node, and each node's writes were durable as soon as it ran, so the received act's own entry stood whatever the effects did after it.

ADR-0146 made an embargo act atomic: the act's entries, the case-file changes they carry and every consequence a later node commits (the stub re-issue, a proposal's relay) commit in one DataLayer transaction, or none of them is written.
A trigger act is atomic by that rule.
A received act was not: its own entry was committed before the transaction of its consequences opened.
When a consequence failed, the entry stayed committed without them, a state no single act produces.
The change the entry carries, such as the register step of a received proposal, had to be applied again after the rollback, so the CASE_MANAGER held what every replica copies from the entry.
A received proposal whose relay failed then stayed in the register with no consent rows and no Invites.
Its redelivery was refused, because the rows it needs did not exist, and nothing relayed it.

Where does the received act's own entry commit, so that a received act succeeds or fails as a whole?

## Decision Drivers

- An act's consequences commit all at once or not at all; no repair pass and no later run or redelivery finishes an act (ADR-0146).
- A received act and a trigger act follow the same rule.
- The stage order of a received tree is unchanged: the guards judge the activity before anything is committed, and the act's entry comes before its consequences (CLP-07-013, CLP-10-006).
- This is a prototype: no recovery machinery for a state that atomicity can rule out.

## Considered Options

- **A — The guarded commit of the received activity and the effects after it run in one DataLayer transaction.**
- **B — Keep the commit in its own transaction, and apply the entry's change again when the consequences roll back.**
- **C — Move the commit after the effects, so the entry commits last.**

## Decision Outcome

Chosen option: **A, one transaction for the act's own entry and its consequences**, because it is the only option that makes a received act atomic without recovery machinery.

### Decision details

1. **The commit and the effects are one act.**
   In a received tree whose effects commit consequences of the act, the guarded commit of the received activity, the replica effects and the CASE_MANAGER effects run as one composite node, an `ActTransaction`, inside one DataLayer transaction.
   When any of them fails or raises, nothing any of them wrote is kept: not the act's own entry, its announcements, the consent rows, nor a relayed or re-issued Invite.
2. **The stage order stands.**
   Intake, the door guards, the clock decisions and the precondition guards run before the transaction opens, in the order ADR-0111 and ADR-0135 set.
   The commit is still the first node of the act and the effects follow it.
   Only the durability of the commit changes: it becomes durable when the act commits, not when the commit stage runs.
3. **What stays outside the act.**
   Intake's archive of the received activity is a record of receipt, not of the act, so it stands when the act rolls back (ADR-0111, CLP-10-018).
   A clock decision commits the CASE_MANAGER's own decision ahead of the guards, and is its own act (CLP-10-025).
   A refusal answers a delivery that the guards refused, so no act runs (CLP-10-022).
4. **A failed received act leaves no trace but intake's archive.**
   Because no entry is kept, the idempotency guards that read the ledger do not see the act: a later delivery of the activity is not stopped as a repeat, and runs the act again.
   Nothing redelivers it on its own, and nothing re-applies a change after a rollback.
   The failure is an internal error: the handler raises, and the inbox, which answered the sender before processing, logs it.
5. **The act block is the same at every receiver.**
   At a participant replica the commit gate skips, and the block holds the replica effects, such as storing a received Invite's embargo and queuing the replica's answer.
   A failure among them keeps none of their writes either, so a received act fails as a whole at a replica too.
6. **The received-tree factory composes it.**
   A tree asks for the act block through the factory (`create_receive_activity_tree(as_one_act=True)`), which needs a commit stage; no tree builds its own.
   Every received embargo tree that commits does so.
   Whether other received trees do is decided per tree, with the case trees that still commit an embargo consequence after their act (#4959).

This record supersedes detail 1 of ADR-0111 in part.
That detail set four stages, intake, guards, guarded commit and effects, and each was composed as its own node.
The order stands; for a tree that passes the act block, the guarded commit and the effects now run as one transaction instead of as separate writes.
The rest of ADR-0111 stands.

### Consequences

- Good, because a received act and a trigger act now follow one rule: the act succeeds or fails as a whole.
- Good, because the re-apply after a rollback is removed, and no committed entry can exist without its consequences.
- Good, because a received act whose consequence fails leaves no entry, so a received proposal is never stuck in the register with no rows, and a later delivery of it runs the act again.
- Bad, because the transaction now also holds the store's write lock for the received act's own commit and its replica effects, so another writer on the same store waits longer.
- Bad, because a failure in a replica effect at the CASE_MANAGER now also removes the act's entry, where before it left the entry committed.
  This is the intended outcome: the act did not complete.
- Bad, because the sender is not told that its act failed: the inbox answered before processing, and a refusal notice answers only a guard's refusal.
  This was already so before this record; it now means the act is wholly absent rather than half done.

## Validation

- A test fails a received withdrawal's consent-row commit and asserts that no row is saved and the `Leave`'s own entry is not kept.
- A test fails a received proposal's relay part-way and asserts that the proposal keeps no entry, no row, no relayed Invite and no register step, and that a redelivery is applied and relayed.
- `test/architecture/test_embargo_consequences_in_one_act.py` asserts that every received embargo tree commits its own entry inside an `ActTransaction`.
- `test/core/behaviors/case/test_receive_activity_tree.py` asserts the factory puts the commit, the replica effects and the CASE_MANAGER gate in one `ActTransaction`, and refuses the option on a tree with no commit.
- `test/core/behaviors/test_act_transaction.py` asserts that at a participant replica a failing replica effect keeps none of the replica effects' writes.

## Pros and Cons of the Options

### A — One transaction for the act's own entry and its consequences

- Good, because the act is atomic, and nothing has to repair it.
- Good, because the stage order and the ledger and sync shape do not change.
- Bad, because the write lock is held for longer.

### B — Keep the commit in its own transaction, and re-apply its change after a rollback

- Good, because the commit stage is durable as soon as it runs, as before.
- Bad, because it leaves an entry committed without its consequences, a state no single act produces.
- Bad, because the re-apply is recovery machinery, and it cannot recreate the consequences, so a received proposal stays in the register with no rows and its redelivery is refused.

### C — Commit the received act's own entry after its effects

- Good, because a failed effect leaves no entry.
- Bad, because the act's entry no longer comes first, against CLP-07-013, and each effect's own entry would precede the entry of the act that caused it.
- Bad, because the effects would write before the commit, against CLP-10-006.

## More Information

- ADR-0111 — intake is the first received-side stage; detail 1 is superseded in part here.
- ADR-0135 — compose received trees, never chain them.
- ADR-0146 — one atomic commit per embargo act.
- #4933 — the implementation.
- #4959 — the case trees that still commit an embargo consequence after their act.

Generated spec requirements: `case-ledger-processing.yaml` CLP-07-015.
