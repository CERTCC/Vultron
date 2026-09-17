!!! warning "Open question: do Participants acknowledge delivery?"

    The delivery log of the CASE_MANAGER records each message that it sent, and the time.
    It cannot record which messages the Participants received.
    A Participant can send a receipt activity when a message arrives.
    The log then shows the difference between confirmed delivery and best-effort delivery.
    Retry logic then has better data than a time-out.

    Receipts have a cost in message volume.
    Thus receipts are optional, not mandatory.
    A prototype can record its delivery attempts and supply no receipts.
    But the architecture lets a later version add receipts without a change to the core protocol.

    The activity type for a receipt is unsettled.
    `Read` is too strong, because it shows that the Participant processed the activity.
    A `Receive` or `Ack` activity is the weaker statement.
    It also gives the delivery log the data that the log needs.
