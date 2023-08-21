# Implementation Notes

While a complete MPCVD protocol implementation specification is out of scope for this report, we do have a few 
additional suggestions for future implementations.
In this chapter, we describe an abstract case object for use in tracking MPCVD cases.
Next, we touch on the core MPCVD protocol subprocesses (RM, EM, and CS), including how the CS model might integrate with
other processes.
Finally, we provide a few general notes on future implementations.

## General Notes

The protocol and data structures outlined in this report are intended to
facilitate interoperability among individual organizations' workflow
management systems. As such, they are focused on the exchange of
information and data necessary for the MPCVD process to function and will not likely
be sufficient to fully address any individual organization's
vulnerability response process.

We conclude the chapter with a few general implementation notes.

### Message Formats {#sec:msg_formats}

We defined a number of message types in
§[\[sec:protocol_message_types\]](#sec:protocol_message_types){reference-type="ref"
reference="sec:protocol_message_types"} and showed how they fit into a
case in §[1.1](#sec:case_object){reference-type="ref"
reference="sec:case_object"}, but we did not specify any format for
these messages. Message formats can be thought of as two related
problems:

##### Structure and Semantic Content of Each Message Type.

In addition to the commentary throughout this chapter, messages will
likely need to have some sort of consistent header information and some
content specifically designed to address the semantic needs of each
message type. Such a format must include fields, datatypes, and an
underlying formatting structure.

##### Container Syntax for Messaging and Data Exchange.

While we have a predilection for JSON Schema-defined formats, other format
specifications (e.g., XSD or protobuf) could serve implementers' needs just as
well. In fact, to the degree possible, it seems preferable for the
container syntax to remain a late-binding decision in implementation. As
long as the structure and semantics are well defined, most standard data
formats should be adaptable to the task.

-   MPCVD
    Protocol Messages SHOULD use well-defined format specifications
    (e.g., JSON
    Schema, protobuf, XSD).

We anticipate that emerging formats like the OASIS
CSAF [@csaf-docs; @csaf-oasis] and ontologies
like the NIST
Vulnerability Data Ontology (Vulntology){== [@vulntology] ==} will play a part.

### Transport Protocol {#sec:transport_protocol}

We have not specified how MPCVD protocol implementations connect to each
other. Presumably, technologies such as REST APIs or WebSockets would be leading candidates
to resolve this gap. However, other system architectures could be
adapted as well. For example, an XMPP message-routing system might be desired,
or even blockchain-related technologies might be adaptable to portions
of this protocol as well.

-   MPCVD
    Protocol Implementations SHOULD use common API patterns (e.g.,
    REST,
    WebSockets).

### Identity Management {#sec:identity_mgt}

We have not addressed Participant authentication as part of the
protocol, but obviously implementers will need to determine how
Participants know who they are talking to. Individual user accounts with
multi-factor authentication are the de facto standard for modern
CVD tools, but in
an interoperable MPCVD world, the assumption of centralized
identity management may not be practical. Federated identity protocols
such as OAuth, SAML, and/or OpenID Connect may be useful.
