---
status: accepted-provisional
date: 2026-10-26
created: 2026-10-26
updated: 2026-10-26
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0107; design interview of 2026-10-26 on issue #4976
informed: []
stakeholder_type: [project-contributor]
---

# An Actor Known Only by URI Travels as an Id-and-Type Reference, and No One Invents a Value They Do Not Know

## Context and Problem Statement

Several activities carry an actor as their `object` or `target`: the actor recommendation `Offer(Actor)`, the stub and full-case `Invite(Actor)`, and the Offers of an ownership transfer and of a role delegation.
A sender often knows that actor only by its URI.
Addressing a peer by URI alone is allowed, and a fully resolved actor record is an enrichment, not a precondition (AKM-05-001).

The activity factories turned such a URI into a whole actor object.
It carried `published` and `updated` times read from the sender's clock, and `inbox` and `outbox` collections whose addresses were derived from the actor's id.
Nobody had asserted any of those values.
A receiver that recorded the activity now held them as if the actor had published them, and the case ledger carried them in its snapshots.
A rebuild of the same activity minted new times, so two builds of one activity disagreed.

Three rules pulled against each other.
The stub rule (MV-10-001) forbids a partial inline object for any type but the case.
This codebase carries the `object` of every activity inline (AKM-03-003), because receivers route an activity by its object's `type`, and a bare URI has none.
Fetching an object named by URI (AKM-05-003) would let a receiver resolve a bare URI, but no receiver here does it yet.

How should an actor travel in an activity when the sender knows only its URI?

## Decision Drivers

- A receiver routes `Offer(Actor)` apart from `Offer(Report)` by the object's `type`, so the object must carry a `type` it can read without a fetch.
- Inviting or recommending a peer on another node must keep working when the sender holds nothing but the peer's URI (AKM-05-001).
- Nothing in an activity, or in a record, may claim a value that nobody asserted.
- Rebuilding an activity under the id an earlier attempt used must produce the same body (OX-06-002).

## Considered Options

- An id-and-type actor reference when only the URI is known
- A bare URI in `object`, resolved by fetching
- The full held profile, or refuse to send

## Decision Outcome

Chosen option: "An id-and-type actor reference when only the URI is known", because it is the only option that keeps type-based routing, keeps cross-node invitations, and claims nothing the sender does not know.

The decision rests on one general rule: an implementation never records or sends a value it does not know, and a field whose value it does not know stays absent.
The actor reference applies that rule to the case of a sender that knows only the URI.

A sender carries the actor profile it holds, as it holds it.
When it holds nothing more than the URI, it carries an actor reference: an inline object with exactly an `id` and a `type`.
A receiver reads the missing fields of a reference as unknown, never as erased, so a reference never replaces a fuller record the receiver holds.

The general rule binds the records a sender keeps as well.
A peer's address-book record carries only what the peer's profile supplied.
A clock time the recording node read, or an endpoint it derived from the id, is not part of the peer's profile.

Delivery is addressing, not a recorded value.
A sender delivers to the `inbox` its held profile of the recipient names, and falls back to the inbox address derived from the recipient's URI only when it holds no inbox.

### Consequences

- Good, because no activity or record carries a time or address that nobody asserted.
- Good, because a rebuild of an activity that names an actor produces the same body every time.
- Good, because a receiver still routes by the reference's `type` without fetching anything.
- Good, because a peer known only by URI can still be invited or recommended.
- Neutral, because the stub rule gains a second narrow exception, the actor reference, beside the case stub.
- Bad, because a receiver given only a reference learns no more about the actor than its id until object fetching exists.

## Validation

Factory tests check the body an activity carries for an actor given by URI and for an actor given as a held profile.
A demo test checks that the actors the demos name travel as full seeded profiles, not as references.

## Pros and Cons of the Options

### An id-and-type actor reference when only the URI is known

- Good, because the reference carries a `type`, so routing needs no fetch.
- Good, because it states exactly what the sender knows and nothing more.
- Neutral, because receivers must read a reference's missing fields as unknown.

### A bare URI in `object`, resolved by fetching

This option makes actors an exception to the inline-object rule of this codebase and relies on the receiver fetching the actor (ADR-0107).

- Good, because it is the plain ActivityPub form.
- Bad, because a receiver cannot route an activity whose object has no `type` until it has fetched the object, and no receiver here fetches yet.
- Bad, because the change waits on the object-fetching work.

### The full held profile, or refuse to send

- Good, because every actor that travels is a full profile.
- Bad, because a sender that knows a peer only by URI could no longer invite or recommend it, which AKM-05-001 allows.

## More Information

Generated spec requirements: `actor-knowledge-model.yaml` AKM-02-006 and AKM-05-005; `message-validation.yaml` MV-10-001 (amended); `outbox.yaml` OX-12-009.
