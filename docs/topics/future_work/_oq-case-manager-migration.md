!!! warning "Open question: where is the enacting actor after an ownership transfer?"

    A case ownership transfer moves the `CASE_OWNER` role from one actor to another actor.
    It uses an `Offer` and `Accept` handshake through the CASE_MANAGER (ADR-0053).
    The handshake does not set the location of the actor that enacts CASE_MANAGER.
    If the organization of the new owner administers the case, there are two results.
    The enacting actor moves to that organization, or it stays in position and the previous organization continues to hold a part in the case.

    There are four possible methods, and the project has not selected one.

    **Migration** changes the URI of the actor and tells each participant the new URI.
    This method is clear.
    It also controls the messages that are in transit and the replicas that use the previous URI.

    **A proxy** keeps the previous instance, which forwards each message to the new instance.
    This method is simple.
    But if a second ownership transfer occurs, the chain of proxies becomes longer.

    **An HTTP 301 redirect with an AS2 `Move`** keeps the initial URI as the canonical URI.
    A new instance answers at that URI.
    ActivityPub defines this mechanism for actor migration.

    **A new actor**, with the previous actor in a frozen condition, is the minimum work to build.
    It is also the largest risk to verification.
    New key material breaks the continuity of signatures across the transfer.

    The redirect method is the most practical method from the current data.
    This is a working preference, not a decision.
