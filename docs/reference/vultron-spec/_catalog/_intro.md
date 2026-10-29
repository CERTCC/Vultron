## 14. Requirements Catalog [N]

This section holds the normative requirements of the protocol.
It lists every requirement of the `protocol` and `foundation` tiers once, and the row it gives a requirement is the one every other page links.
The sections before it show a requirement as a callout where their text discusses it, and each callout links the requirement's row here.

The `protocol` tier is the Vultron layer: the rules that bind every implementation, in any language, that takes part in Vultron.
It covers the forms Vultron messages take on the wire, including where ActivityStreams 2.0 (AS2) allows several forms and Vultron asks for one.
It also covers which messages are sent and when, what a receiver does given its state, including on duplicate delivery, and the state machines underlying those behaviors.

The `foundation` tier holds the rules Vultron inherits unchanged from the standards beneath it: AS2, ActivityPub, and the Hypertext Transfer Protocol (HTTP).
They have a subsection of their own, §14.8 Inherited Requirements, and an implementer reads them together with the `protocol` tier.

The `protocol` tier is grouped by theme into seven subsections, from §14.1 Vultron Protocol to §14.7 Transport and Security.
Within a subsection, each requirement file has a heading of its own, and its requirements are listed group by group.
Each row gives the requirement's ID, its priority, its statement and rationale, and the requirements it relates to.
