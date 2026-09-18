!!! warning "Open question: who controls the Vultron vocabulary?"

    Vultron adds its own object and activity types to AS2.
    It declares them as JSON-LD `@context` extensions.
    An extension vocabulary that more than one organization uses needs a version and governance model.
    Vultron does not have one.

    Three parts are unresolved.
    The first part is the procedure to propose and to ratify a new activity type or object type, and the group that does it.
    The second part is the method for two instances to agree at peering time on the vocabulary versions that both instances support.
    A peer that does not recognize a type cannot act on that type.
    The third part is the URI of the `@context` document and the operator that hosts it.
    A `@context` document that a peer can resolve makes the vocabulary interoperable instead of local.

    Concern [#3368](https://github.com/CERTCC/Vultron/issues/3368) records this question.
