!!! warning "Open question: how strong are the necessary ordering guarantees?"

    Ledger fanout does not occur immediately.
    The CASE_MANAGER relays a Case Ledger Entry to Participants on more than one instance.
    For a short time, those Participants can see the activities in different sequences.

    Eventual consistency is sufficient.
    No part of the protocol uses the sequence of arrival.
    The `logIndex` value of each entry holds the correct sequence.
    A Participant that receives entries 1, 2, 3, and 5 finds that entry 4 is missing.
    It buffers entry 5, and ledger reconciliation delivers entry 4 (SYNC-00-007, ADR-0037).
    The Participant does not use a history that has missing entries.
    Gap detection replaces delivery order.

    One point is not tested.
    The project does not know if a coordination decision needs a stronger guarantee than eventual consistency.

    Concern [#3364](https://github.com/CERTCC/Vultron/issues/3364) records this question.
