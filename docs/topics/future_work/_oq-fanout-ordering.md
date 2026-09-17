!!! warning "Open question: how strong do the ordering guarantees need to be?"

    Fan-out is not instantaneous.
    When the CASE_MANAGER relays a journal entry to Participants across several instances, those Participants can see activities in different orders for a while.

    Eventual consistency looks sufficient, and the protocol should be built so that nothing depends on arrival order.
    The journal sequence numbers carry the ordering, so a Participant that receives entries 1, 2, 3, and 5 can detect that 4 is missing and pull the gap rather than act on an incomplete history.
    Gap detection replaces delivery ordering.

    What has not been tested is whether any coordination decision genuinely needs a stronger guarantee than that.
