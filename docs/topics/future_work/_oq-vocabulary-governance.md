!!! warning "Open question: who governs the Vultron vocabulary?"

    Vultron extends AS2 with its own object and activity types, declared as JSON-LD `@context` extensions.
    An extension vocabulary that more than one organization implements needs a versioning and governance story, and Vultron does not have one yet.

    Three parts are unresolved.
    The first is how a new activity or object type gets proposed and ratified, and by whom.
    The second is how two instances agree during peering on which vocabulary versions they both support, since a peer that does not recognize a type cannot act on it.
    The third is which URI the `@context` document lives at and who commits to hosting it, because a resolvable context is what makes the vocabulary interoperable rather than local.
