---
status: proposed
date: 2026-10-16
created: 2026-10-16
updated: 2026-10-16
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0111, ADR-0119, ADR-0122, ADR-0124;
  specs/case-ledger-processing.yaml CLP-07-013, CLP-07-014;
  specs/case-management.yaml CM-23-016
informed: []
stakeholder_type: [project-contributor]
---

# An Embargo Act Stores Its Planned Entries Before It Commits, and the Next Run Finishes Them

## Context and Problem Statement

Every change the CASE_MANAGER makes to the case file is its own ledger entry, and the act's entry comes first (CLP-07-013, ADR-0124).
So one embargo act commits several entries: the act's own, then one `Create` or `Update(EmbargoConsent)` for each consent row it changes.
The CASE_MANAGER decides every row before the first commit, then commits the entries one at a time.

When a later commit fails, the entries already committed stay committed, and their changes are saved, so no change is ever made without its entry.
The case is then in a state no single act produces.
A proposal can be in the register while some participant holds no row for it, which every later read of that proposal refuses (ADR-0122).
A relayed Invite can be committed while the invitee's row was never moved to `INVITED`, so the invitee's answer is checked against the wrong starting state.

Nothing finishes the act.
A repeated trigger starts a new act, and a redelivered received act is stopped by its idempotency guard.
One act, the stub re-issue, has its own repair pass that re-derives the row it owes; no other act has one.

The question this record settles: how does the CASE_MANAGER finish an act whose later entries did not commit?

## Decision Drivers

- An act's entries are decided once, before the first commit; a later run must commit what was decided, not decide again from a clock or policy that has moved on.
- A received act's own entry is committed by intake, before the act's tree decides its consequences (ADR-0111).
- Replicas receive entries one `Announce(CaseLedgerEntry)` at a time and apply them by copying (CM-23-016).
- The CASE_MANAGER's working records are case bookkeeping, never ledgered or replicated (CLP-07-014).
- The entries that follow an act have ids derived from the act and the row they change, so committing one again lands on the same entry.
- One recovery rule for every embargo act, not one repair pass per act.

## Considered Options

- **A — Store the planned entries before the first commit; the next CASE_MANAGER embargo run on the case finishes them.**
- **B — Re-derive the owed entries from the committed act, one repair pass per act, as the stub re-issue does.**
- **C — Commit the act and its consequences as one ledger append.**
- **D — Leave the state and make readers tolerate a missing or unmoved row.**

For where the finishing step runs under A:

- **A1 — First in every CASE_MANAGER embargo tree for the case, received and trigger alike, before its guards.**
- **A2 — First in every CASE_MANAGER tree for the case.**
- **A3 — Inside the shared commit step, before it commits a new act.**

## Decision Outcome

Chosen option: **A, with A1**.

Before an embargo act's first commit, the CASE_MANAGER stores a record of the act and every entry it still owes, each row carried in full as decided.
The record is case bookkeeping: it is not ledgered and not replicated.
The finishing step reads it only to commit the entries already decided, unchanged; it never reads the record to decide a case-file value, so CLP-07-014 holds, and a replica learns each row from its committed entry alone.
It is removed when the act's last entry commits.

Each CASE_MANAGER embargo tree for the case starts by finishing every open record for that case, before its guards read any row.
When the act's own entry is in the ledger, the step commits the entries the record still owes, in their planned order, and applies them.
When the act's own entry is not in the ledger, the act never happened, and the step discards the record.
The step needs no ordering with the act's first commit beyond "store, then commit", because a record whose act did not commit is recognised and discarded.

The stub re-issue's own repair pass is replaced by this step wherever its replacement's row goes through the same plan.

Option B was rejected: each act needs its own re-derivation, and a re-derivation can decide a different row than the first run did once the clock or local policy has changed, such as an RSVP deadline.
Option C was rejected: a received act's entry is committed by intake before its consequences are decided, so it cannot join their append, and a batch needs a new ledger and sync shape for replicas.
Option D was rejected: every register entry has a row on every participant (ADR-0122), and an unmoved row misjudges a later answer.
Option A2 was rejected: only embargo trees read consent rows, so finishing in every other tree adds work to every case act without protecting a reader.
Option A3 was rejected: a received act's guards read the rows before the shared commit step runs, so the step would finish too late.

### Consequences

- Good, because a failed commit in the middle of an act no longer leaves a case the CASE_MANAGER cannot work.
- Good, because the finished act commits exactly the entries the first run decided.
- Good, because one step covers every embargo act that changes more than one record.
- Bad, because the CASE_MANAGER stores one more kind of bookkeeping record.
- Bad, because a half-finished act stays visible on every node until the next CASE_MANAGER embargo tree runs for the case.

## Validation

- A test fails an act's second commit, then runs a CASE_MANAGER embargo tree for the case, and asserts the owed entries are committed in their planned order and the case file equals the one a run with no failure produces.
- A test stores a record whose act's entry is not in the ledger and asserts the finishing step discards it and commits nothing.
- The rebuild-from-ledger check holds on a replica after the act is finished.

## More Information

- ADR-0122 — per-embargo participant consent and the embargo register.
- ADR-0124 — every change to the case file is an entry, and replicas copy.
- #4764 — the concern this record answers.

Generated spec requirements: `case-ledger-processing.yaml` CLP-07-015.
