---
status: proposed
date: 2026-11-16
created: 2026-11-16
updated: 2026-11-16
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0122, ADR-0124, ADR-0201, ADR-0203;
  notes/embargo-lifecycle.md, notes/as2-vocabulary-alignment.md;
  issue #6246
informed: []
partially_supersedes:
  - 0122-per-embargo-participant-consent.md
stakeholder_type: [project-contributor]
---

# An Embargo Stores Its Own Status, and the Register Is the Case's Ordered List of Embargoes

## Context and Problem Statement

An embargo holds only its terms: start, end and case.
Its status, the embargo a revision replaced, and the record of how it ended are stored beside it, on the case's embargo register entry: ADR-0122's `(embargo, status, replaces)`, with the termination recorded beside it.
When an embargo ends, the embargo object itself therefore does not change, so a message that says "this embargo changed" has nothing on the embargo to point at.

Where are the facts about one embargo stored?

## Decision Drivers

- Every fact about an object belongs on that object, so a message about the object can state the change, and nothing is held in two places.
- Every state is named and stored, and embargo management state stays a read of the stored records (ADR-0122).
- An event's status lives on the event itself, as event platforms carry it (FEP-8a8e, `eventStatus`).

## Considered Options

- The embargo stores its status, revision link and termination, and the register lists embargoes
- The register keeps them, and the embargo's wire form shows a copy
- The register entry becomes an addressable object of its own

## Decision Outcome

Chosen option: "The embargo stores its status, revision link and termination, and the register lists embargoes", because it keeps every fact about an embargo on the embargo and in one place.

An embargo stores three fields beyond its terms:

- `status`, one of the statuses ADR-0122 defines: `PROPOSED`, `ACTIVE`, `REJECTED`, `SUPERSEDED`, `CANCELLED`, `TERMINATED`;
- `replaces`, the embargo an activated revision replaced;
- the termination, once terminated: the cause kind, the act that caused it when known, and a human reason.

The case's embargo register is its ordered list of embargoes, appended and not removed.
A copy of the case carries that list, each embargo in a form ADR-0198 allows for an object slot.
ADR-0122's statuses, triggers and invariants stand; they now range over the embargoes' own `status` fields.
Embargo management state is derived from them, as before.
Every change of an embargo's status happens in a ledgered act, as one of ADR-0122's register steps, so its history is in the ledger; how an embargo's end is sent is ADR-0203.

### Consequences

- Good, because a message about an embargo's status can be an `Update` of the embargo itself.
- Good, because nothing about an embargo is duplicated, so no check is needed that two copies agree.
- Bad, because the stored case schema changes, and every reader of a register entry moves to the embargo's fields.

## Validation

- A model test asserts that an embargo stores `status`, `replaces` and its termination, and refuses a termination on an embargo that is not terminated.
- The register's invariant tests run over the embargoes' `status` fields.
- A replica seeded with a whole case reads each embargo's status and termination from the embargo.

## Pros and Cons of the Options

### The embargo stores its status, revision link and termination, and the register lists embargoes

- Good, because each fact has one home, on the thing it describes.
- Bad, because it is a stored-schema change.

### The register keeps them, and the embargo's wire form shows a copy

- Good, because storage does not change.
- Bad, because the same facts appear twice on the wire, and a receiver must refuse a copy that disagrees with the register.

### The register entry becomes an addressable object of its own

- Good, because it names exactly the record that changes.
- Bad, because it invents a Vultron object no outside reader knows, to hold facts that belong to the embargo.

## More Information

This record partially supersedes ADR-0122 in where an embargo's status, revision link and termination are stored.
ADR-0122's per-embargo consent, its statuses, triggers and invariants, and its rule that embargo management state is derived from stored records stand.
The embargo's wire type is ADR-0201; how an embargo's end is sent is ADR-0203.
