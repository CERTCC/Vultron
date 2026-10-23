"""
Shared inbox driving adapter — stub.

Handles ActivityPub shared-inbox delivery — a single endpoint that accepts
activities addressed to multiple local actors and fans them out to per-actor
inboxes.

Future implementation will:

1. Validate the HTTP Signature on the inbound request.
2. Identify the addressed local actors from the activity ``to``/``cc`` fields.
3. Enqueue one inbox delivery per addressed actor via the delivery queue port.

The shared inbox is a driving adapter because it triggers the core (fan-out
use case), but it also interacts with the driven delivery queue adapter.
"""


class SharedInboxAdapter:
    """Future ActivityPub shared-inbox adapter.

    This adapter is intentionally unimplemented until the full OX-11 shared
    inbox fan-out design (signature validation + per-actor fan-out queueing)
    is ready to land.
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "SharedInboxAdapter is not implemented yet "
            "(specs/outbox.yaml OX-11-001 through OX-11-004)."
        )
