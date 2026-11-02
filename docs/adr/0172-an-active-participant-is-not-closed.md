---
status: proposed
date: 2026-11-02
created: 2026-11-02
updated: 2026-11-02
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; CONCERN-5574; ADR-0114, ADR-0116;
  specs/case-management.yaml CM-10-004, CM-10-007, CM-21-021, CM-23-004,
  CM-23-018, CM-23-020, CM-31-002, CM-31-003, CM-31-009, CM-31-013;
  specs/sync-ledger-replication.yaml SYNC-03-005
informed: []
partially_supersedes:
- 0114-joining-a-case-stub-invite-inert-participant.md
- 0116-removing-a-participant-withdraws-entitlement-not-membership.md
stakeholder_type: [project-contributor]
---

# An Active Participant Is Not Closed

## Context and Problem Statement

A participant is **active** when it has joined the case, has not been removed, and, while an embargo is in force, is a signatory to it.
ADR-0114 and ADR-0116 both left RM `CLOSED` out of that test on purpose.
A participant that has left still had to receive the ledger entries that record its own closure, and the last of those is fanned out after its status already reads `CLOSED`.

So "active" and "closed" became two separate axes.
Every rule that means "may still act on the case or receive new content" has to say "active and not closed", and a rule that says only "active" quietly includes participants who have left.
The ownership-transfer rule was one: as written, it let a closed participant be offered the case, and only the code's combined test refused it.
The published `activeParticipants` collection is another: it lists closed participants, although ADR-0116 says it shows who receives case content now.

Should "active" exclude closed participants, with the deliveries a closed participant is still owed named as exceptions?

## Decision Drivers

- A rule author who writes "active participant" means a participant that may still act and receive new case content; the term should mean that without a qualifier.
- Nearly every entitlement decision already uses the combined "active and not closed" test, so the broad meaning serves a few deliveries, not the rules.
- The deliveries a closed participant is still owed are few and fixed: the entries that record its own closure, the resync that recovers them, and the direct notice to a signatory that an embargo ended early.
- One published view of who is active should agree with the term every rule uses.

## Considered Options

- Narrow "active" to exclude closed participants, and name the closure deliveries as exceptions
- Keep "active" broad, and coin a separate term for "active and not closed"
- Keep "active" broad, and lint for rules that use it without saying whether closed participants count

## Decision Outcome

Chosen option: "Narrow 'active' to exclude closed participants, and name the closure deliveries as exceptions", because it makes the word mean what rule authors already take it to mean, and it moves the burden of remembering from every rule onto the few deliveries owed to a closed participant.

### Active means not closed

A participant is active when it has joined the case, has not been removed, its closure is not recorded in the case's ledger, and, while an embargo is in force, it is a signatory to that embargo.
Every other participant is inert.
A closed participant is inert, as a removed one is, and like a removed one it is not sent the Invites that ask an inert participant to join or to consent.
Its participant record stays on the roster.

### What a closed participant is still owed

Three deliveries reach a closed participant, and each is named where it is required rather than inferred from "active":

1. The ledger entries that record its own closure, identified by their subject being that participant.
   They reach it only if it was entitled to case content apart from its closure; they never widen entitlement.
2. A replay of those same entries, when it asks for a resync with `Reject(CaseLedgerEntry)`.
   The resync guard admits a closed participant on the same "entitled apart from its closure" test, and the replay is capped at its own closure entries.
3. The direct notice to a closed signatory that the embargo it is bound by was terminated or shortened.
   That notice carries no other case content and never depended on the active test.

Nothing else reaches a closed participant, and it may act on nothing else.

### The published collection follows the term

The case's `activeParticipants` collection holds exactly the active participants, so closed participants leave it when their closure is recorded.
No separate collection of invited, removed or closed participants is published.
The roster carries every participant record inline, with its join, removal and status history, and the ledger records when each closure happened; a reader that wants who was ever in the case reads those.

### Consequences

- Good, because a rule that says "active participant" no longer includes participants that have left, so the defect the ownership-transfer rule had cannot recur by omission.
- Good, because the published `activeParticipants` agrees with the entitlement every send and every sender guard applies.
- Good, because the deliveries owed to a closed participant are named in one place each, instead of being the unstated reason the term stayed broad.
- Bad, because the broad test survives under another name for the closure entries and their resync, and a rule that needs it must name it.
- Bad, because the serialized case changes: a case with a closed participant publishes a shorter `activeParticipants`, and recorded demo transcripts that pinned the old value change with it.
- Neutral, because ADR-0114's and ADR-0116's other decisions (the stub Invite, the inert record, removal as a stored fact) are unchanged; only their statement that RM `CLOSED` is not part of the active check is replaced.

## Validation

- A test closes a participant and finds it no longer active, absent from the published `activeParticipants`, refused as a sender, and sent no further case content.
- A test finds the closing participant still receives every entry that records its own closure, the last one included, and that a participant inert or removed when it left receives none of them.
- A test finds a closed participant's `Reject(CaseLedgerEntry)` answered with a replay capped at its own closure entries.
- A test finds a closed signatory still sent the direct notice when the embargo it agreed to is terminated or shortened.

## Pros and Cons of the Options

### Narrow "active" to exclude closed participants

- Good, because the term means what rule authors already assume.
- Good, because the code's common test and the term become the same thing.
- Bad, because the closure entries and their resync need a named broad test of their own.
- Bad, because the published collection changes on the wire.

### Keep "active" broad, and coin a separate term for "active and not closed"

- Good, because nothing on the wire changes.
- Bad, because authors must choose between two near-synonyms, and the shorter, more natural one is the wrong one for most rules.
- Bad, because the published `activeParticipants` keeps disagreeing with the meaning most rules need.

### Keep "active" broad, and lint for unqualified uses

- Good, because it is the smallest change.
- Bad, because a lint can find the phrase but cannot tell whether the author meant to include closed participants, so it still relies on review.
- Bad, because it leaves the defect's cause, a term broader than its common use, in place.

## More Information

This record replaces one decision in each of ADR-0114 and ADR-0116: that RM `CLOSED` is not part of the active check.
Their other decisions stand.

Generated spec requirements: CM-10-004, CM-10-007, CM-21-021, CM-23-004, CM-23-018, CM-23-020, CM-31-002, CM-31-003, CM-31-013, SYNC-03-005.
