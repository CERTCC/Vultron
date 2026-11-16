---
status: proposed
date: 2026-11-16
created: 2026-11-16
updated: 2026-11-16
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0107, ADR-0124, ADR-0137;
  specs/sync-ledger-replication.yaml SYNC-16, SYNC-17, SYNC-18;
  specs/message-semantics-mapping.yaml MSM-05;
  notes/as2-vocabulary-alignment.md; issue #6247
informed: []
partially_supersedes:
  - 0137-case-records-are-attached-by-one-message-never-created-first.md
  - 0155-a-participant-states-its-ledger-position-and-the-case-manager-answers-a-lag.md
stakeholder_type: [project-contributor]
---

# The Case Ledger and Status Histories Are Named Ordered Collections

## Context and Problem Statement

The CASE_MANAGER publishes each ledger commit as `Announce(CaseLedgerEntry)`.
That message carries no `context`, so the case is only inside the entry, and the ledger it extends has no name.
The sender of an act gets no positive acknowledgement: the entry that later commits it does not say that it answers that act.
A participant states its ledger position with a `Read` of a bare entry id, the only message whose object is a bare id.
A participant that holds nothing asks for a replay with a `Reject` that has no object.
A status goes out as `Add(ParticipantStatus)[target=CaseParticipant]` or `Add(CaseStatus)[target=VulnerabilityCase]`, which name the record they are added to but not a history.

How do the ledger and the status histories go on the wire, so that a replica reads each message without inference?

## Decision Drivers

- `Add` says something was added to a collection, and the collection is its `target` (VOC Add); `Announce` only calls attention to an object.
- An answer names what it answers (VOC `inReplyTo`).
- Every case activity carries `context` = the case (`notes/activitystreams-semantics.md`).
- Status records are not updated; a new status is added to a history, one message form per act (ADR-0137).
- One form per message, with no exceptions in the pattern rules.

## Considered Options

- Named ordered collections, with an `Add` to them that acknowledges the act it commits
- `Announce(CaseLedgerEntry)` with `context` added, and a separate acknowledgement message
- No change

## Decision Outcome

Chosen option: "Named ordered collections, with an `Add` to them that acknowledges the act it commits", because each message then says what it does in AS2's own terms, and the acknowledgement costs no extra message.

### The ledger is a named ordered collection

A case's ledger has the identity `<case>/ledger`, an `OrderedCollection` whose items are its entries in order, positioned by their log index.
This is identity only: it opens no fetch surface.

### A commit is an Add that acknowledges the act

The CASE_MANAGER publishes each commit as `Add(CaseLedgerEntry, target=<case>/ledger)`, with `context` the case and `inReplyTo` the committed act.
That `Add` is the positive acknowledgement of the act; there is no separate acknowledgement message, and a refusal stays the refusal notice.
The `Add` lists nothing in `result`.
An act that a commit causes names its cause in its own `inReplyTo`, so causation is read from effect to cause, with no ids made in advance and no waiting.

### A position statement is a Read of the ledger

A participant states its position with `Read(<case>/ledger)` carrying `ledgerPosition`.
The empty ledger's position, log index −1 with the case's genesis hash, says the sender holds no entry; the CASE_MANAGER replays every entry after the stated position.
This replaces the `Read` of a bare entry id and the objectless `Reject`.
A gap in the chain is still answered with `Reject(CaseLedgerEntry)`, which now names the `Add` in `inReplyTo`.

### Status histories are named ordered collections

Each participant's statuses are `<participant>/statuses`, and the case's are `<case>/statuses`, both ordered collections with identity only.
A participant asserts a status with `Add(ParticipantStatus, target=<participant>/statuses)`; the CASE_MANAGER records a case status with `Add(CaseStatus, target=<case>/statuses)`.
The newest item is the current status.

### Consequences

- Good, because a replica reads the case, the collection and the position from each message.
- Good, because the sender of an act learns that it committed, from the message that commits it.
- Good, because no pattern needs a bare object id or an objectless activity.
- Bad, because replication, position statements, replay and the status messages all change form, with their patterns, examples and message reference; pre-1.0, the old forms are replaced outright.

## Validation

- A test asserts that a commit goes out as `Add(CaseLedgerEntry, target=<case>/ledger)` with `context` the case and `inReplyTo` the committed act.
- A test asserts that `Read(<case>/ledger)` at −1 replays the whole ledger, and that no pattern accepts a bare object id or an objectless `Reject`.
- A test asserts both status `Add` forms name their history in `target` and the case in `context`.

## Pros and Cons of the Options

### Named ordered collections, with an `Add` to them that acknowledges the act it commits

- Good, because every message uses AS2's own verbs and slots.
- Bad, because many message forms change at once.

### `Announce(CaseLedgerEntry)` with `context` added, and a separate acknowledgement message

- Good, because replication keeps its form.
- Bad, because it adds a message per act, and `Announce` still does not say the entry was added to anything.

### No change

- Good, because nothing changes.
- Bad, because the ledger keeps its unnamed collection, its bare-id `Read` and its objectless `Reject`.

## More Information

ADR-0107 and ADR-0124 name `Announce(CaseLedgerEntry)` as the replication message.
Their decisions, that an entry is a postmark on the received envelope and that a case is a projection of its ledger, stand; only the message's form changes.
ADR-0156 names `Announce(CaseLedgerEntry)` and `Read(CaseLedgerEntry)` in its position rules; its rule that case activities state the sender's position stands, now over these forms.
A fetchable ledger, `GET <case>/ledger` in pages, is separate work (#5089).

This record partially supersedes ADR-0137 in the `target` of a status `Add`, now the named history rather than the participant or the case; its rule that a record is attached by one message stands.
It partially supersedes ADR-0155 in the form of a position statement, now a `Read` of the ledger rather than of the last entry applied; its rule that a participant states its position and the CASE_MANAGER answers a lag stands.
