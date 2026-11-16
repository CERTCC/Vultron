---
status: accepted-provisional
date: 2026-11-13
created: 2026-11-13
updated: 2026-11-13
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0103; ADR-0159; ADR-0165; planning interview of
  2026-11-13 on issues #5266 and #5480
informed: []
partially_supersedes:
  - 0103-object-time-is-carried-never-minted.md
  - 0159-an-actor-known-only-by-uri-travels-as-an-id-and-type-reference.md
stakeholder_type: [project-contributor]
---

# An Object Slot Holds a Whole Object, a Typed Reference or a URI, and a Received Whole Object Carries Its Time

## Context and Problem Statement

An activity names other objects in its slots: `object`, `target`, `context` and the rest.
A receiver reads each slot in one of the ways ActivityStreams 2.0 allows: an inline object, or a URI.
Two narrow shapes sit between those.
An actor known only by URI travels as `{id, type}` (ADR-0159), and a participant's act on a case names the case the same way (ADR-0165).
For every other type, a sender inlines the whole object or sends a bare URI.

That leaves two gaps.

A receiver routes an activity by its object's `type`.
Given a bare URI it cannot tell an `Announce` of an embargo from an `Announce` of a case, so it must fetch the object before it can classify the activity at all (AKM-05-007).
A typed reference would let it classify first.

A partial inline object, one that carries `id`, `type` and some but not all of its class's fields, is accepted for several types today.
For `CaseParticipant` the parser even fills the missing status with defaults (#5265).
Nothing tells the receiver whether the sender meant a reference or sent a broken object.

The second gap is time.
ADR-0103 carries a received object's missing `published` as absent and refuses it only where a decision reads it: a case's genesis, an embargo's end, a replicated ledger entry, and a case status (CLP-15-010).
Every new reader of an object's time must first ask whether its type is one of those, and the absent value travels into core as a `None` that core code must guard against.

What may a slot hold, how does a receiver tell the forms apart, and must a received object carry its time?

## Decision Drivers

- A receiver must classify an activity by its object's type, and should not fetch an object it already holds just to learn the type.
- A receiver must still cope with a bare URI (SE-01-002).
- A reference is never the object: a handler that needs the content uses the object it holds, or fetches it (ARCH-25-009, AKM-05-007).
- The shape of an inline object alone must say whether it is a reference or a whole object, so a broken object is refused rather than read as a reference.
- Nothing may record a value nobody asserted (ADR-0159), and a receiver never substitutes its own clock for a sender's time (ADR-0103).
- Core should receive non-optional types where the protocol can require them (ADR-0032).

## Considered Options

- Three forms, told apart by shape; a received whole object carries its time
- Keep the two narrow references; refuse missing times per decision
- Allow partial inline objects and read every missing field as unknown

## Decision Outcome

Chosen option: "Three forms, told apart by shape; a received whole object carries its time", because it is the only option that lets a receiver classify by type without a fetch and tell a reference from a broken object by its keys alone.
It also removes the per-type list of objects whose time is required.

An object slot a receiver reads holds one of three forms:

- **A whole object.** It is complete for its class, and the receiver validates it in full.
- **A typed reference.** It is an inline object with exactly `id` and `type`, and optionally an AS2 `preview`.
  It names an object of that type and claims nothing else about it.
- **A URI**, or a `Link` that carries one.

The forms are told apart by shape.
An inline object with exactly `id` and `type`, with or without `preview`, is a typed reference.
An inline object with any other key is a whole object, and a whole object missing a field its class requires is refused, never read as a reference and never completed with defaults.

A receiver routes an activity by a typed reference's `type` as it routes by a whole object's.
It never reads the reference as the object.
A handler that needs the object's content uses the object the receiver holds.
When the receiver lacks it, the receiver fetches it from its holder and holds the activity until the fetch settles, by the fetch path that already serves case proposals and embargo revisions (AKM-05-007, AKM-05-010).

A preview is a limited view of the object for a recipient that may not hold it (ADR-0193).
What a preview may carry is decided per type, by the work that defines that type's preview.
Until a type's preview is defined, a typed reference of that type that carries a `preview` is refused.

This decision is about what a receiver accepts.
This codebase's senders keep inlining the object of every outbound activity (AKM-03-003), apart from the references ADR-0159 and ADR-0165 already allow.
Which senders move to typed references is later, separate work.

A received whole object carries its `published` time, and one that does not is refused at message validation, as an activity without one already is (CLP-15-008).
Two kinds of whole object are exempt: an actor profile and a collection.
They describe an actor or a container, not an act made at a moment, and many ActivityPub servers serve profiles without `published`.
A typed reference, a URI and a `Link` carry no time, so the rule does not reach them.
`updated` stays optional, and is carried as received when present.
A ledger entry's `payloadSnapshot` is kept as the received JSON and is not validated into objects (CLP-07-011), so the objects nested in it are untouched by the rule.

This partly supersedes ADR-0103.
Its ruling that a received time is carried as sent, never replaced by the receiver's clock, stands.
Its ruling that an absent `published` on a received object is carried inward as absent no longer applies to a whole object of a type that is not exempt.
It also widens ADR-0159: the id-and-type form is no longer an exception for actors alone.

### Consequences

- Good, because a receiver can classify an activity whose object it does not hold, and fetches only when a handler needs the content.
- Good, because a partial inline object is refused rather than read as a reference or completed with invented state, which is the fix #5265 needs.
- Good, because a reader of a received object's `published` no longer checks whether its type is one of the refused ones, and the core classes every author stamps can declare `published` as required.
- Good, because the case stub can become the `preview` of a typed case reference (#6244) without a second shape rule.
- Neutral, because the case stub keeps its own type and position rules until #6244 moves it.
- Bad, because a peer that sends a whole object without `published`, which AS2 allows, is now refused.
  That is the intended trade: a conformant sender stamps every object it authors (CLP-15-006 for activities), and the refusal names the field.
- Bad, because a typed reference to an object the receiver lacks costs a fetch, and a fetch that fails leaves the activity to be refused by the path that needs the object (AKM-05-015).
  A fetch queue that resolves references ahead of handling may be needed later; nothing here builds one.

## Validation

Parse-edge tests feed raw activities through `parse_activity` and the extractor.
They check that a typed reference of each type routes by its type and is never read as the object, and that a reference with a `preview` its type does not define is refused.
They check that a whole object of a non-exempt type with no `published` is refused, naming its position, and that an actor profile or collection without one is accepted.

## Pros and Cons of the Options

### Three forms, told apart by shape; a received whole object carries its time

- Good, because the shape of the keys alone says which form an object is, so the parser needs no per-type exception list.
- Good, because it follows AS2's own vocabulary: `preview` is the AS2 property for a limited view.
- Bad, because a sender may no longer send a partial object as a hint, and must send a reference or the whole object.

### Keep the two narrow references; refuse missing times per decision

- Good, because nothing changes.
- Bad, because a receiver still fetches before it can classify an activity naming a non-actor, non-case object by URI.
- Bad, because a partial inline object stays ambiguous, and the parser keeps reading some of them as whole objects.
- Bad, because each new reader of an object's time must check the per-decision list, and core keeps guarding `None`.

### Allow partial inline objects and read every missing field as unknown

This extends the actor-reference reading (AKM-05-018) to every field of every type.

- Good, because a sender can send whatever it knows.
- Bad, because a receiver cannot tell a field the sender chose to leave out from one it forgot, so a broken object is accepted as a partial one.
- Bad, because every core class would need every field optional, which is the guard-at-every-call-site pattern ADR-0032 removed.

## More Information

ADR-0159 (actor reference) and ADR-0165 (typed case reference) are the two narrow cases this generalizes.
ADR-0193 decides that only a preview may carry a `Redacted` marker.
Issue #6257 tracks previews beyond the case stub, and #6244 moves the stub into a case reference's `preview`.

Generated spec requirements: `message-validation.yaml` MV-10-009 (amended), MV-10-011 and MV-10-012; `case-ledger-processing.yaml` CLP-15-007 (amended) and CLP-15-011.
