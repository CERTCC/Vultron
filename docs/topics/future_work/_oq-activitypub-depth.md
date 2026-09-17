!!! warning "Open question: how deep into ActivityPub should a deployment go?"

    Vultron adopts AS2 as its message vocabulary and borrows ActivityPub's actor, inbox, and outbox primitives.
    The prototype stops there.
    It does not implement the rest of the ActivityPub server surface: no NodeInfo document, no publicly readable outbox collection, no followers or following collections, no shared inbox, and no client-to-server API.

    None of that is ruled out.
    The prototype did not need it to demonstrate coordination between known peers, so the depth of ActivityPub conformance a production deployment should target is still open.
    The trade-off is interoperability with existing fediverse infrastructure against the cost of implementing and securing endpoints that a closed set of trusted peers never reads.

    Two paths are under consideration ([#2068](https://github.com/CERTCC/Vultron/issues/2068)).
    A deployment can harden the existing AS2 endpoints toward full ActivityPub conformance, or it can layer Vultron on top of an existing ActivityPub server and act as an application above it.
    Conformance test coverage, maintainability, fit with the behavior-tree core, and deployment footprint are the criteria for choosing.
