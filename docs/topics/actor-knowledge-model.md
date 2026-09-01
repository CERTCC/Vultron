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

## The full-inline-object rule

When an actor sends an activity, the recipient will try to understand it.
To understand it, the recipient needs the objects the activity refers to.

If the sender puts only a URI in the activity's `object` field, the
recipient cannot resolve it. The recipient has no access to the sender's
data store, so it cannot fetch the object from there. If it has never
received that object before, the URI is meaningless.

This is why the protocol requires full inline objects in outbound activities
(AKM-02-001, AKM-02-002):

> **Every outbound activity must carry its `object` field as a fully
> inline typed object, not as a bare URI.**

The recipient receives the full object alongside the activity that references
it, so no external lookup is needed.

### The one approved exception

The `target` field of an `Invite` activity in selective-disclosure scenarios
is permitted to carry an object reference rather than a fully inline object.
This is the only approved exception to the full-inline-object rule (AKM-02-003).

All other outbound initiating activities — `Create`, `Offer`, `Invite`,
`Announce`, `Add`, `Remove`, `Update`, `Join`, `Ignore`, `Leave` — must carry
a fully inline typed object (AKM-03-001).

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

> *Can the recipient understand this activity using only what it has already
> received from me, plus what is inline in this message?*

If the answer is no — because the activity contains a bare URI that the
recipient has never seen — the activity will fail at the recipient.
The recipient will not be able to pattern-match it, will not be able to
extract meaningful state, and will likely treat it as an unknown or
malformed message.

Building an implementation that passes this test requires constructing
activities with full objects at the point of creation, not after the fact.
The failure mode — a bare URI where an object is expected — is silent in
many frameworks: the activity serialises, is transmitted, and arrives
looking syntactically valid. The failure only appears when the recipient
tries to act on it.

---

## Actor addressing and knowledge

A related implication: knowing a peer's URI is sufficient to address a
message to that peer. You do not need a local record of the peer actor's
profile to send them an activity (AKM-05-001).

An actor that has never interacted with a peer before may still invite that
peer to a case, send them a message, or transfer ownership to them — as long
as it has a valid deliverable URI. Fetching or storing the peer's actor
profile is an enrichment step, not a precondition for protocol participation.

---

## Summary

| Principle | Statement |
|---|---|
| Private data store | Each actor's data store is private. No other actor can access it. |
| Bounded knowledge | What an actor knows is limited to what it has received. |
| Full inline objects | Outbound activities must carry fully inline objects, not bare URIs. |
| One exception | The `target` field of `Invite` may carry a reference in selective-disclosure scenarios. |
| Co-located actors | Co-location does not relax the isolation rule. Use the wire protocol. |
| Addressing | A URI is sufficient to address a peer. A local actor record is enrichment only. |

---

## Further reading

- [Protocol Event Flow](protocol_flow.md) — the actor model that the AKM extends
- [Formal Protocol](../reference/formal_protocol/index.md) — normative protocol requirements
- [Actor Knowledge Model spec](../reference/specs/protocol.md#akm) — the normative AKM requirements (AKM-01 through AKM-05)
