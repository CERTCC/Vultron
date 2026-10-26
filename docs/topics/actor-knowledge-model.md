---
stakeholder_type: [platform-developer]
level: 300
page_type: explanation
---

# Actor Knowledge Model

This page explains a foundational invariant of the Vultron protocol: an
actor's knowledge of the world is bounded entirely by what it has received
via ActivityStreams Activities. Understanding this invariant is essential for
anyone implementing the protocol, in any language or framework.

---

## The invariant

Every actor in Vultron maintains its own private data store. That store is
not accessible to any other actor — not even an actor running on the same
server or in the same process. There is no shared memory. There is no back
channel. There is no way for one actor to look something up in another
actor's store.

This means that what an actor knows about the world is determined entirely
by what it has received:

> **An actor's knowledge is bounded by the AS2 Activities it has received.**

That is the Actor Knowledge Model (AKM). It is not a performance preference.
It is not an optimization to avoid network round-trips. It is the
architectural invariant on which the protocol is built.

---

## Why it follows from the actor model

The [Protocol Event Flow](protocol_flow.md) page describes how each actor
has an inbox and an outbox: messages arrive, the actor processes them, and
results go out. No actor reaches into another actor's state directly.

The AKM is the knowledge-layer consequence of that model. If an actor cannot
reach another's state, then the only way to learn something about the world
outside itself is to receive a message that contains it. Receiving an
activity is the only way to learn that something exists.

This has a concrete corollary for activity construction.

---

## A recipient must be able to obtain what a message names

When an actor sends an activity, the recipient will try to understand it.
To understand it, the recipient needs the objects the activity refers to.

ActivityStreams 2.0 lets an activity carry an object inline or name it by URI, and a receiver copes with either form (SE-01-002).
A URI helps the recipient only if it already holds the object or can fetch it.
The recipient has no access to the sender's data store, so fetching means asking the actor that holds the object through an API call, which is object dereference (AKM-05-003).

So the protocol rule is about whether the recipient can obtain the object, not about which form carries it (AKM-02-002):

> **An object the recipient cannot be expected to hold travels inline, or by a reference the recipient can dereference.**

Every outbound initiating activity — `Create`, `Offer`, `Invite`, `Announce`, `Add`, `Remove`, `Update`, `Join`, `Ignore`, `Leave` — carries the domain object it acts on as its `object`, in either form (AKM-03-001).
A production implementation must support dereference (AKM-05-004).

### Where the protocol requires one form

The `target` field carries a case by reference only: the case URI when the recipient already holds the case, or a case stub for an actor that does not yet hold it (AKM-02-003).
The [protocol specification §12.2 Invitation and Acceptance](../reference/vultron-spec/interactions.md#122-invitation-and-acceptance-n) defines what a case stub carries.

A case ledger entry's payload snapshot records the asserted activity exactly as it was sent, so its nested objects are inline where the sender inlined them and by URI where the sender named them (CLP-07-006).
The entry hash covers the snapshot and nothing outside it, which is why the case manager never fills a reference in: the record would then be its reconstruction rather than what was sent.

### What the reference implementation does

The reference implementation dereferences only a few references (AKM-05-007).
A participant fetches a case object it lacks from the case manager when an activity cannot be classified without it.
A replica fetches the embargo that an announced revision replaces.
The case manager fetches a proposer's profile that the proposal names by its URI.
It still carries every outbound `object` inline, and a bare URI it cannot fetch is refused where the object is needed (AKM-02-004, AKM-03-003).
That is a shortcut of the prototype, not a Vultron rule; an implementation that dereferences may send references wherever the protocol allows them.

---

## Co-located actors still use the wire

The AKM applies even when two actors are running in the same process or on
the same server. Co-located actors MUST communicate via the wire protocol
and MUST NOT exchange information through direct data-store access or
in-process calls that bypass the inbox and outbox (AKM-01-002).

This is easy to get wrong when building a prototype: it is tempting to let
two actors share a data structure when they are in the same process.
Doing so violates the AKM. It couples the actors in a way that breaks as
soon as they are separated, and it means the system's behavior in a
distributed deployment cannot be inferred from its behavior in a single
process.

The isolation is architectural. Keep it, even when co-location makes
shortcutting it convenient.

---

## What this means for implementers

The practical test for any outbound activity is:

> *Can the recipient understand this activity using only what it has already received from me, what is inline in this message, and what it can dereference?*

If the answer is no — because the activity names by URI an object the recipient has never seen and cannot fetch — the activity will fail at the recipient.
The recipient will not be able to pattern-match it, will not be able to extract meaningful state, and will likely treat it as an unknown or malformed message.

The failure mode is silent in many frameworks: the activity serializes, is transmitted, and arrives looking syntactically valid.
The failure only appears when the recipient tries to act on it.
An implementation that dereferences little or nothing, like the reference implementation, avoids it by constructing activities with full objects at the point of creation.

---

## Actor addressing and knowledge

A related implication: knowing a peer's URI is sufficient to address a
message to that peer. You do not need a local record of the peer actor's
profile to send them an activity (AKM-05-001).

An actor that has never interacted with a peer before may still invite that
peer to a case, send them a message, or transfer ownership to them — as long
as it has a valid deliverable URI. Fetching or storing the peer's actor
profile is an enrichment step, not a precondition for protocol participation.

An activity that names such a peer as its `object` or `target` still carries it inline, because a receiver routes an activity by its object's `type`.
The sender carries the actor profile it holds, unchanged.
When it holds only the URI, it carries an *actor reference*: an inline object with exactly the actor's `id` and a `type` (AKM-05-005).
A receiver reads the fields an actor reference lacks as unknown, so a reference never replaces a fuller record of that actor the receiver already holds.

The actor reference follows from a general rule: an actor never records or sends a value it does not know (AKM-02-006).
A field whose value it does not know stays absent.
A `published` time read from the sender's own clock, or an `inbox` address guessed from another actor's id, is such a value.
A receiver cannot tell an invented value from an asserted one.

---

## Summary

| Principle | Statement |
|---|---|
| Private data store | Each actor's data store is private. No other actor can access it. |
| Bounded knowledge | What an actor knows is limited to what it has received. |
| Obtainable objects | An object the recipient cannot hold already travels inline, or by a reference it can dereference. |
| Case in `target` | A case in `target` is its URI or a case stub, never the full case. |
| Ledger snapshots | A ledger entry's payload snapshot carries its nested objects in full. |
| Reference implementation | Inlines every outbound object, because it dereferences only a few references. |
| Co-located actors | Co-location does not relax the isolation rule. Use the wire protocol. |
| Addressing | A URI is sufficient to address a peer. A local actor record is enrichment only. |
| Actor references | An actor travels as the sender's held profile, or as an id-and-type reference when only its URI is known. |
| Known values only | No actor records or sends a value it does not know. An unknown field stays absent. |

---

## Further reading

- [Protocol Event Flow](protocol_flow.md) — the actor model that the AKM extends
- [Formal Protocol](../reference/formal_protocol/index.md) — normative protocol requirements
- [Actor Knowledge Model spec](../reference/specs/protocol.md#akm) — the normative AKM requirements (AKM-01 through AKM-05)
