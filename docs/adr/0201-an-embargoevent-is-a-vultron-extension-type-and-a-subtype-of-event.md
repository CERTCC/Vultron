---
status: proposed
date: 2026-11-16
created: 2026-11-16
updated: 2026-11-16
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0194, ADR-0196, ADR-0202;
  notes/activitystreams-semantics.md, notes/as2-vocabulary-alignment.md;
  issue #6246
informed: []
stakeholder_type: [project-contributor]
---

# An EmbargoEvent Is a Vultron Extension Type and a Subtype of Event

## Context and Problem Statement

An embargo goes on the wire as `"type": "EmbargoEvent"` alone.
A generic ActivityStreams 2.0 reader does not know that type, so it cannot tell that an embargo is an event with a start and an end.
An embargo is also about to carry fields of its own that a plain AS2 `Event` lacks: its status, the embargo a revision replaces, and why it ended (ADR-0202).

How does an embargo identify itself on the wire, so that a generic reader sees an `Event` and a Vultron reader sees an embargo?

## Decision Drivers

- An extension type carries the core type it overlaps, so a generic AS2 reader still understands the object (AS2 Core § Extensibility; `notes/activitystreams-semantics.md` § "Choosing AS2 Terms").
- A field AS2 does not define needs a JSON-LD term, so a JSON-LD processor keeps it (ADR-0194).
- A refusal notice already uses this form: `"type": ["Refuse", "Reject"]` (ADR-0196).

## Considered Options

- A Vultron extension type, a subtype of `Event`, written as a type list
- A plain AS2 `Event` with Vultron fields
- `"type": "EmbargoEvent"` alone, as today

## Decision Outcome

Chosen option: "A Vultron extension type, a subtype of `Event`, written as a type list", because it is the only option in which both a generic reader and a Vultron reader read the object correctly.

An embargo is written as `"type": ["EmbargoEvent", "Event"]`.
`EmbargoEvent` is a Vultron type defined as a subtype of `Event` in the Vultron vocabulary.
A receiver resolves the type list, either order, or `"EmbargoEvent"` alone, to the embargo type, as ADR-0196 does for `Refuse`.
Every field an embargo carries beyond `Event`'s gets a JSON-LD term.

### Consequences

- Good, because a generic reader sees an `Event` with `startTime` and `endTime`, and a Vultron reader sees an embargo.
- Good, because it reuses the type-list handling the refusal notice already needs.
- Bad, because every embargo on the wire, in examples and in recordings changes its `type`; pre-1.0, the old form is replaced outright.

## Validation

- A parser test resolves `["EmbargoEvent", "Event"]`, `["Event", "EmbargoEvent"]` and `"EmbargoEvent"` to the embargo type.
- A serialization test asserts that an embargo is written with `"type": ["EmbargoEvent", "Event"]`.
- The JSON-LD term check covers every embargo field.

## Pros and Cons of the Options

### A Vultron extension type, a subtype of `Event`, written as a type list

- Good, because a generic reader and a Vultron reader both read it.
- Bad, because a type list is harder to match than a single string.

### A plain AS2 `Event` with Vultron fields

- Good, because the type is one plain AS2 word.
- Bad, because a Vultron reader cannot tell an embargo from any other event without looking at its fields.

### `"type": "EmbargoEvent"` alone, as today

- Good, because nothing changes.
- Bad, because a generic reader does not recognize the object at all.
