!!! warning "Open question: how strong are the necessary ordering guarantees?"

    Ledger fanout does not occur immediately.
    The CASE_MANAGER relays a Case Ledger Entry to Participants on more than one instance.
    For a short time, those Participants can see the activities in different sequences.

    Eventual consistency is sufficient.
    No part of the protocol uses the sequence of arrival.
    The `log_index` value of each entry holds the correct sequence.
    A Participant that receives entries 1, 2, 3, and 5 finds that entry 4 is missing.
    It then pulls the missing entry, and it does not use a history that has missing entries.
    Gap detection replaces delivery order.

    One point is not tested.
    The project does not know if a coordination decision needs a stronger guarantee than eventual consistency.
