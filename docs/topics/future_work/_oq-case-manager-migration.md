!!! warning "Open question: where does the enacting actor live after ownership transfers?"

    Case ownership transfer moves the `CASE_OWNER` role from one actor to another through an `Offer` and `Accept` handshake routed through the CASE_MANAGER (ADR-0053).
    That handshake does not settle where the actor *enacting* CASE_MANAGER lives afterward.
    If the new owner's organization is to administer the case, the enacting actor either moves to that organization or stays where it is and keeps the previous one involved.

    Four options are open, and none has been chosen.
    **Migration** changes the actor's URI and notifies every participant.
    It is clean, and it has to account for messages already in flight and for replicas that still address the old URI.
    **Proxying** leaves the previous instance forwarding to the new one.
    It is simple until ownership transfers a second time and the forwarding chain grows.
    **An HTTP 301 redirect paired with an AS2 `Move`** keeps the original URI canonical while a new instance answers it, and borrows a mechanism ActivityPub already defines for actor migration.
    **Provisioning a fresh actor** and freezing the previous one is the least work to build and the most disruptive to verification, because new key material breaks signature continuity across the transfer.

    The redirect option looks most pragmatic on current evidence.
    That is a working preference, not a decision.
