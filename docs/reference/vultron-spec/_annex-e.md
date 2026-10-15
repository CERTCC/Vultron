## Annex E — Relationship to ActivityPub [I]

Vultron uses the ActivityStreams 2.0 vocabulary as its wire format.
This version does not require full ActivityPub server behavior; the roadmap is at [§1.3 Relationship to Existing Standards](introduction.md#13-relationship-to-existing-standards).

Where Vultron follows ActivityPub conventions:

- Actors are identified by Uniform Resource Identifier (URI) and expose an inbox and an outbox.
- Messages are Activities with `type`, `actor`, `object` and `id`.
- Delivery is a Hypertext Transfer Protocol (HTTP) POST to the recipient's inbox.

Where Vultron adds constraints ActivityPub does not impose:

- Case-scoped messages route through the participant holding the Case Manager role rather than directly between participants ([§5.4.2 Routing Topology](layers.md#542-routing-topology)).
- A case ledger entry's payload snapshot MUST carry its nested objects inline rather than by reference ([§5.5 Serialization](layers.md#55-serialization)), because the entry hash covers only what the snapshot carries.
- The Vultron vocabulary extends the ActivityStreams vocabulary with the object types of [§5.2 Object Types](layers.md#52-object-types).

!!! info "See also"
    - [Vultron ActivityStreams (AS) Activity Guides](../../howto/activitypub/activities/index.md) — how to carry out each protocol flow
