!!! warning "Open question: how much of ActivityPub does a deployment implement?"

    Vultron uses AS2 as its message vocabulary.
    It also uses the actor, inbox, and outbox primitives from ActivityPub.
    The prototype stops there.
    It does not supply the other parts of an ActivityPub server:

    - a NodeInfo document
    - a public outbox collection
    - followers and following collections
    - a shared inbox
    - a client-to-server API

    The project does not reject these parts.
    The prototype does not need them to show coordination between known peers.
    Thus the correct depth of ActivityPub conformance for a production deployment is open.
    Full conformance gives interoperability with existing fediverse tools.
    It also has a cost.
    A deployment makes endpoints that a closed group of trusted peers does not read, and it gives them protection.

    There are two possible paths ([#2068](https://github.com/CERTCC/Vultron/issues/2068)).
    A deployment can make the current AS2 endpoints fully conformant to ActivityPub.
    As an alternative, it can put Vultron above an existing ActivityPub server.
    Four criteria apply to this selection: conformance test coverage, maintainability, agreement with the behavior-tree core, and deployment footprint.
