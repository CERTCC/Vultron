# General Implementation Notes

{% include-markdown "../includes/not_normative.md" %}

Here we provide a few general implementation notes.

## Message Formats

We defined a number of [message types](../reference/formal_protocol/messages.md) in the formal protocol, and showed how they
fit into a [case object](case_object.md), but we did not specify any format for these messages.
Message formats can be thought of as two related problems:

### Structure and Semantic Content of Each Message Type

In addition to the commentary throughout this section, messages will likely need to have some sort of consistent header
information and some content specifically designed to address the semantic needs of each message type.
Such a format must include fields, datatypes, and an underlying formatting structure.

### Container Syntax for Messaging and Data Exchange

While we have a predilection for JSON Schema-defined formats, other format specifications (e.g., XSD or protobuf) could
serve implementers' needs just as well.
In fact, to the degree possible, it seems preferable for the container syntax to remain a late-binding decision in implementation.
As long as the structure and semantics are well defined, most standard data formats should be adaptable to the task.

!!! info "ActivityPub and Vultron"

    While an complete Vultron implementation remains a work in progress, we have made some progress
    on translating the Vultron Protocol into an ActivityPub-based semantics. 
    Our initial efforts so far indicate that ActivityPub could be a good fit for the Vultron Protocol.
    The message formats discussion above
    and transport protocl below are addressed by ActivityPub directly, and the last two (identity management and 
    encryption) might be better addressed in the context of ActivityPub rather than reinventing the wheel.
    See [Vultron ActivityPub](./activitypub/index.md) for more information. 

<!-- hr to force spacing -->
----

!!! note ""  

    Vultron Protocol Messages SHOULD use well-defined format specifications (e.g., JSON Schema, protobuf, XSD).

!!! tip "Related formats and ontologies"

    We anticipate that emerging formats like the [OASIS CSAF](https://oasis-open.github.io/csaf-documentation/) and ontologies
    like the [NIST Vulnerability Data Ontology](https://github.com/usnistgov/vulntology) ([Vulntology](https://github.com/usnistgov/vulntology)) will play a part.

## Transport Protocol

We have not specified how Vultron Protocol implementations connect to each other.
Presumably, technologies such as REST APIs or WebSockets would be leading candidates to resolve this gap.
However, other system architectures could be adapted as well.
For example, an XMPP message-routing system might be desired, or even blockchain-related technologies might be adaptable
to portions of this protocol as well.

!!! note ""

    Vultron Protocol Implementations SHOULD use common API patterns (e.g., REST, WebSockets).

## Identity Management

We have not addressed Participant authentication as part of the protocol, but obviously implementers will need to
determine how Participants know who they are talking to.
Individual user accounts with multi-factor authentication are the de facto standard for modern CVD tools, but in
an interoperable MPCVD world, the assumption of centralized identity management may not be practical.

!!! tip "Related Identity Standards"

    Federated identity protocols such as [OAuth](https://oauth.net/), [SAML](https://saml.xml.org/about-saml), and/or [OpenID Connect](https://openid.net/developers/how-connect-works/) may be useful.

## Encryption

The protocol does not specify any encryption requirements, but it is likely that some form of encryption will be
necessary for Vultron Protocol implementations.

### Protecting Data in Transit

It may be sufficient for implementations to rely on transport-layer encryption (e.g., TLS), but end-to-end encryption
may be desirable in some cases.
For now at least, we leave this decision to implementers.

!!! note ""

    Vultron Protocol Implementations SHOULD use transport-layer encryption to protect sensitive data in transit.

!!! note ""

    Vultron Protocol Implementations MAY use end-to-end encryption to protect sensitive data in transit.

### Protecting Data at Rest

Encryption at rest is likely to be a requirement for many implementations.
Again, we leave this decision to implementers.

!!! note ""

    Vultron Protocol Implementations MAY use encryption to protect sensitive data at rest.
