## Annex E — Relationship to ActivityPub [I]

Vultron uses the ActivityStreams 2.0 vocabulary as its wire format. This version
does not require full ActivityPub server behavior; the roadmap is at
[§1.3](index.md#13-relationship-to-existing-standards).

Where Vultron follows ActivityPub conventions:

- Actors are identified by URI and expose an inbox and an outbox.
- Messages are Activities with `type`, `actor`, `object` and `id`.
- Delivery is an HTTP POST to the recipient's inbox.

Where Vultron adds constraints ActivityPub does not impose:

- Case-scoped messages route through the participant holding the Case Manager
  role rather than directly between participants
  ([§5.4.2](index.md#542-routing-topology)).
- An activity MUST carry its object inline rather than by reference
  ([§4.8](index.md#47-knowledge-model-and-actor-isolation)), because a
  participant's knowledge must not depend on another participant being reachable.
- The Vultron vocabulary extends the ActivityStreams vocabulary with the object
  types of [§5.2](index.md#52-object-types).

!!! info "See also"
    - [Vultron AS Activity Guides](../../howto/activitypub/activities/index.md) —
      how to carry out each protocol flow
