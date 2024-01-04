---
status: accepted
date: 2023-12-01
deciders: adh
informed: CERT/CC (CERT Coordination Center) Vulnerability Analysis Team
---

# Use ActivityStreams Vocabulary as the basis for Vultron Message Formats

## Context and Problem Statement

The Vultron protocol specifies a number of required message types.
These message types are used to communicate state changes and other information
between Vultron agents.
The message types are defined in the formal Vultron protocol specification.

However, the protocol specification does not define the message format.
The message format is the structure of the message itself.

What format should be used for Vultron messages?

## Decision Drivers

- We need to prototype the Vultron protocol as runnable code.
- We need for Vultron prototype instances to be able to communicate with each
  other.
- We would prefer to use an existing message format rather than invent our own.
- We would prefer to use a message format that is
  - extensible
  - naturally adaptable to the needs of the Vultron protocol
  - well understood
  - well supported
  - widely used
  - well documented
  - easy to implement

## Considered Options

- [JSON](https://www.json.org/json-en.html)
- [ActivityStreams Vocabulary](https://www.w3.org/TR/activitystreams-vocabulary/)
- [JSON-LD](https://json-ld.org/)
- [Protocol Buffers](https://developers.google.com/protocol-buffers)

## Decision Outcome

Chosen option: "ActivityStreams Vocabulary", because it most closely matches the
semantics of the Vultron protocol, is well supported, and is easy to implement.

ActivityStreams Vocabulary is a vocabulary for describing social interactions.
It builds semantics on top of JSON-LD, which builds
semantics on top of JSON.

ActivityStreams Vocabulary is foundational to the ActivityPub protocol, which is
the basis for the Fediverse.
In turn, ActivityPub and its underlying ActivityStreams Vocabulary, is widely
used in the Fediverse, which is a collection of social networking
systems that use the same underlying protocol (e.g., Mastodon and others). We
anticipate that, given widespread adoption of
ActivityStreams Vocabulary as part of the Fediverse, it will be easier to find
libraries and tool
implementations that support it.

### Consequences

- For our prototype, we will use
  the [ActivityStreams Vocabulary](https://www.w3.org/TR/activitystreams-vocabulary/)
  as the basis for our message format.

#### Pros and Cons

- Good, because it is well supported and easy to implement
- Good, because it provides rich semantics that are well suited to the Vultron
  protocol
- Good, because it is widely used and well documented
- Neutral, because its broader success is tied to the success of the Fediverse
- Bad, because it is not as widely used as JSON, JSON-LD, or Protocol Buffers

## Pros and Cons of the Options

### JSON

JSON is a reasonable serialization format for web-based APIs. However, from our
perspective,
it merely provides the serialization syntax but is not expected to provide any
semantics.
This means that any semantics that we want to use in the Vultron protocol would
have to be
defined in software that implements the protocol, and that would make Vultron
more
bespoke and potentially difficult to integrate with other systems.

- Good, because it is well supported and easy to implement
- Bad, because it does not provide any semantics

### JSON-LD

JSON-LD adds data linking semantics to JSON. This is a step in the right
direction, but
does not go as far as we would like.

- Good, because it is well supported and easy to implement
- Bad, because it does not provide the rich semantics that we would like

### Protocol Buffers

Protocol Buffers is a binary serialization format that is well suited to
high-performance
applications. However, it is not well suited to the Vultron protocol, which has
no
specific performance requirements. In addition, like pure JSON, Protocol Buffers
does not provide
any semantics, so we would have to define our own semantics on top of it.

## More Information

- [ActivityStreams Vocabulary](https://www.w3.org/TR/activitystreams-vocabulary/)
- [ActivityPub](https://www.w3.org/TR/activitypub/)
- [Fediverse](https://en.wikipedia.org/wiki/Fediverse)
