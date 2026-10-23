!!! warning "Open question: which HTTP responses a receiving actor returns"
    This version does not say which HTTP status code a receiving actor returns when it refuses a message.
    For example, it does not say whether an invalid activity gets 422, an activity addressed only to other actors gets 400, or a message that cannot be decrypted gets 400.

    One option is for the protocol to specify these responses, so that a sending actor can rely on them and act on them.
    The other is to leave them to each server implementation.
    A Vultron actor built on a stock ActivityPub server returns whatever that server returns, so a protocol rule could conflict with the server it runs on.

    Until this is settled, these codes are recorded as the reference implementation's choices, not as protocol requirements.
    The codes that HTTP itself defines, such as 405 for an unsupported method and 413 for a body that is too large, are not part of this question.
