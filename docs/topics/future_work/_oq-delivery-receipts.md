!!! warning "Open question: should Participants acknowledge delivery?"

    The CASE_MANAGER's delivery log records what it sent and when.
    It cannot record what arrived.
    A receipt activity sent back on delivery would let the log distinguish confirmed delivery from best-effort delivery, and would give retry logic something better than a timeout to work with.

    The cost is message volume, which is why receipts should be optional rather than mandatory.
    A prototype can log delivery attempts and implement no receipts at all, provided receipts can be added later without changing the core protocol.

    The activity type is unsettled.
    `Read` claims too much, because it implies the Participant processed the activity rather than merely received it.
    A `Receive` or `Ack` activity is the lighter claim, and matches what the delivery log actually needs to know.
