---
status: proposed
date: 2026-10-07
created: 2026-10-07
updated: 2026-10-09
revision: 2
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; Concern #4284, Issue #4178, Concern #4425; ADR-0107, ADR-0111,
  ADR-0116, ADR-0119, ADR-0122; specs/case-ledger-processing.yaml CLP-07, CLP-10;
  specs/sync-ledger-replication.yaml SYNC-00-002; specs/case-management.yaml CM-23-016
informed: []
stakeholder_type: [project-contributor]
---

# The Case Is a Projection of Its Ledger: Every Change Is an Entry, and Replicas Copy

## Context and Problem Statement

A participant case replica exists so that a participant can learn the current state of a case by reading its own copy, without asking the CASE_MANAGER for a snapshot each time.
The case ledger is how those copies are kept in step with the CASE_MANAGER's case: the CASE_MANAGER commits entries, and replicas apply them; a replica is synchronized when its ledger tail hash matches the CASE_MANAGER's (SYNC-00-002).

Tracing participant embargo consent for Concern #4284, and the inert invitee's record for Concern #4425, showed that the CASE_MANAGER's case and its replicas are not kept in step by one rule:

- One committed entry often stands for several changes.
  Sending a stub Invite created the invitee's participant record, its consent rows and its roster entry, but only the Invite was committed (#4396 has since given the record its own `create_case_participant` entry).
- Some changes have no entry at all: the create-case trigger, a note attached from a received `Create(Note)`, the CASE_MANAGER's own policy-based embargo consent, and commits that log a failure and carry on.
- Replicas fill the gaps by working the changes out again.
  They mint their own ids, stamp their own clock times, run embargo lifecycle code, and walk the RM transition table from their own stored state.
  A replica's copy of the invitee's record has a different id from the CASE_MANAGER's, and an ownership transfer never moves the CASE_OWNER role on any replica.
- Specs and ADRs assumed one act gives one entry, so the second change an act causes had nowhere to be recorded.
- No test compares a case rebuilt from its ledger with the CASE_MANAGER's case.

Each gap leaves replicas silently disagreeing with the CASE_MANAGER, and each new feature has to remember to add its write in two places.

What is the relationship between the case and its ledger, and how does each node change its copy of the case?

## Decision Drivers

- Two replicas at the same ledger position must hold identical cases, by construction rather than by care.
- A replica infers nothing: what is not in the replicated ledger did not happen.
- A ledger entry records an act that has happened (ADR-0119), never an intention.
- One rule, one implementation: a change written in one place cannot be forgotten in another.
- The CASE_MANAGER is the single writer for its case (the single-writer regime), so no two commits conflict.
- Every claim of consistency should be testable by a test, not maintained by care.

## Considered Options

- Keep two paths: the CASE_MANAGER's own write logic, and a separate replica replay path, kept consistent by tests.
- Commit snapshots: each act's entry carries every record it changed, and a replica overwrites its copy.
- Commit the protocol messages only, and derive every consequence by replaying them with one function used by every node.
- Commit every change as its own message: the act, then one CASE_MANAGER-authored message per change it causes, each carrying the changed object; replicas copy.

## Decision Outcome

Chosen option: "Commit every change as its own message", because it is the only option in which a replica decides nothing, so two replicas at the same ledger position hold the same case without each running the same lifecycle code.

### The case file and case bookkeeping

The **case file** is the state of the case that replicates: report management, participant records and status, the embargo register and participant embargo consent (ADR-0122), notes, reports, and anything added later.
**Case bookkeeping** is what the CASE_MANAGER keeps alongside a case while it works it, such as the record of who recommended whom, offer records and pending markers.
Case bookkeeping is not part of the case file: it is not ledgered, not replicated, and never read to produce a case-file value.

### Every change to the case file is an entry

Every change the CASE_MANAGER makes to the case file is committed as its own case ledger entry, before or as part of making it, and a change with no entry is not made.
Each entry's payload is an AS2 activity (CLP-07-011).

An act and the changes it causes are different facts (CLP-07-002).
The act's entry comes first: the message as received, or the message the CASE_MANAGER sent.
When the act's own activity states a change, the act's entry is that change's entry, and no second entry records it again.
Examples are `Add(Note, target=Case)` with the note inline, and an invitee's `Accept` of the stub Invite, which is the entry for its own consent row and `joined` mark.
Applying such an entry writes only what the activity states, with any time taken from the entry.
Each other change the act causes follows as its own CASE_MANAGER-authored entry, in the order the CASE_MANAGER writes them, and carries the changed object in full (CLP-07-006):

- a record the CASE_MANAGER brings into existence is `Create(Object)`, such as the inert invitee's `Create(CaseParticipant)` (`create_case_participant`) after a stub Invite;
- a changed record is `Update(Object)`, such as the old and new owners' `Update(CaseParticipant)` after an ownership transfer, or a status entry for each RM step a Leave causes (CM-23-001).

The CASE_MANAGER's records of clock-driven acts, such as an expired invitation (CM-28-009), and its decisions from local policy, such as agreeing to a proposal by its own embargo policy, are entries too: attributed to the CASE_MANAGER and committed like any other message.

An object the case file holds must therefore have a wire form.
`EmbargoConsent` and `EmbargoRegisterEntry` become AS2 objects for this reason; their shapes are part of the embargo work under epic #4283.

A message the CASE_MANAGER has no use for receiving is not part of the protocol just because the vocabulary defines it.
Nobody sends `Update(VulnerabilityCase)` to the CASE_MANAGER, so its received path is removed (#4443); the class stays, as the form of the CASE_MANAGER's own entry if it ever changes a case field.

### One apply function, and it copies

One function applies one entry to a case and returns the case after it.
The CASE_MANAGER and every replica use it, and it is the only code that changes the case file.

The function copies:

- It writes the objects the entry carries; it never builds an object the entry does not carry.
- It mints no ids and reads no clock: every id and time in the case file came from an entry.
- It reads no local policy, configuration, case bookkeeping or store state outside the case.
- It runs no lifecycle logic; every consequence of an act arrives as its own entry.
- Where an entry implies a starting state, such as a status change from one RM state to the next, it checks the case against it.
  An entry it cannot apply is refused.
  On a replica that means an earlier entry is missing, which the gap handling resolves (`LedgerGapBuffer`); it is never patched over.

### How the CASE_MANAGER changes its case

The CASE_MANAGER never edits its case directly.
It decides on an act and its consequences, checks them, records them, and only then applies the record:

1. **Decide.** Guards read the current case and refuse the act if it is not allowed.
   Lifecycle logic and local policy run here, and only here, to work out every change the act causes.
2. **Trial apply.** The apply function applies the act's entry and each consequence entry to a copy of the case, and every invariant is checked.
   A refusal here stops the act, and nothing is recorded or sent.
3. **Complete the act.** A received message has already arrived (intake, ADR-0111).
   A message the CASE_MANAGER sends is complete when it is written to its own outbox (ADR-0119).
4. **Commit.** The act's entry, then each consequence entry, is committed to the ledger.
5. **Apply.** The apply function applies the entries to the case.
   A successful trial guarantees this step succeeds, and the trial copy may be kept as the result.
6. **Consequent acts.** Messages sent because of this act follow, each recorded as its own act.
   The `Announce(CaseLedgerEntry)` that replicates an entry is delivery of the record, not an act, and is not itself recorded (CLP-07).

What is committed is the messages, never the modified copy.

This is a narrowing of the received-side order of ADR-0111 (intake, guards, commit, effects): changes to the case file move out of "effects" into the commit and apply steps, and only outside acts remain effects.
It keeps ADR-0119's order for sent messages: the outbox write completes the act, and the commit follows it.
ADR-0119 is itself `proposed`; until it is accepted, the commit-before-outbox rule in `vultron/core/behaviors/case/AGENTS.md` governs today's code, and this ADR's step 3 lands with it.

### A replica

A replica applies each entry it receives, in ledger order, with the same function.
It runs no lifecycle logic of its own and decides nothing about the case file.
Two replicas at the same ledger position therefore hold identical case files, and both equal the CASE_MANAGER's at that position.

This tightens CM-23-016's "MUST NOT derive a transition the ledger does not record": a replica derives nothing, because every change it applies is an entry.

A seeded replica starts from the case snapshot it was seeded with instead of from empty.
The seed must equal the result of applying the ledger up to the entry it was taken at, so seeding is a shortcut through replay, not a second source of state.

### Scope

The rule covers the whole case file.
A domain whose replay does not yet meet it is a defect to fix, not an exception, and the rule has no allow-list.

### Consequences

- Good, because two replicas at the same ledger position hold the same case file by construction.
- Good, because a write cannot be forgotten on one side: there is only one side.
- Good, because a replica never runs lifecycle or policy code, so a change to that code changes only the CASE_MANAGER.
- Good, because "the replica is faithful" becomes a test: replay the ledger into an empty store and compare.
- Good, because a crash between commit and apply loses nothing; applying the ledger restores the case.
- Good, because a missing entry on a replica surfaces as a refused entry or a chain gap, not as silent disagreement.
- Bad, because the ledger grows: one act can commit several entries.
- Bad, because every object the case file holds needs a wire form, and consent rows and register entries do not have one yet.
- Bad, because every case-file write in today's lifecycle and behavior-tree code must become an entry, and every replica step that works a change out must become a copy.
- Neutral, because a replica trusts the CASE_MANAGER's working of each consequence instead of checking it; the single-writer regime already makes the CASE_MANAGER the authority for the case.

## Validation

- A rebuild-from-ledger test replays each demo and integration scenario's CASE_MANAGER ledger into an empty store and asserts the result equals the CASE_MANAGER's case file, including participant records, consent rows and the embargo register.
- A test asserts the apply function reads no clock, mints no id and reads no store outside the case it is given.
- An architecture test asserts that the case file is changed only through the apply function.

## Pros and Cons of the Options

### Two paths kept consistent by tests

- Good, because it is the least rework.
- Bad, because it is the arrangement that produced the gaps in Concerns #4284 and #4425: every new write has to be added twice.

### Commit snapshots

- Good, because a replica only overwrites, so applying is trivial.
- Bad, because one entry carries several facts, so the payload is no longer a single AS2 activity (CLP-07-011).
- Bad, because the ledger stops recording which change happened, only what the records look like afterwards.

### Commit the messages only, derive consequences

This was revision 1 of this ADR.

- Good, because entries stay small: the ledger holds only the protocol's own acts.
- Bad, because every replica must run the same lifecycle code as the CASE_MANAGER, so "same position, same case" holds only as long as every node runs identical code.
- Bad, because some consequences cannot be derived at all: ids the CASE_MANAGER minted, times it stamped, and decisions it took from local policy.
- Bad, because the CASE_MANAGER's own changes that follow from no single message, such as creating an invitee's record, had no entry to be derived from.

### Commit every change as its own message, copy

- Good, because the ledger records every act and every change, and a replica only copies.
- Good, because each entry is still one AS2 activity, with its own hash-chain position, so a missing one is detected.
- Bad, because more entries are committed, and more objects need wire forms.

## More Information

Revision 1 was decided in the maintainer's design session of 2026-10-07, recorded in Concern #4284.
Revision 2, the copy model, was decided in the planning of Concern #4425 on 2026-10-09.
Implementation is tracked under epic #4283: embargo and consent in #4294, RM and participant records in #4295, and the remaining gaps in #4439, #4440, #4441, #4442, #4443 and #4444.
ADR-0122 is the first domain designed against this rule; its activation consequences become consequence entries under #4294.
