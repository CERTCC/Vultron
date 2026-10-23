"""
HTTP delivery driven adapter — stub.

Handles transport of outbound ActivityStreams payloads to remote actor
inboxes via HTTP POST.

Responsibilities (future implementation):

- Receive a serialized AS2 JSON payload and a target inbox URL.
- Sign the request with the local actor's HTTP Signature private key.
- POST the payload to the target inbox.
- Retry on transient failures with exponential back-off.
- Record delivery success/failure in the activity store.

This adapter is transport-only — it must not construct or inspect AS2
objects. Serialization is handled by ``wire/as2/serializer.py`` before
the payload reaches this adapter.
"""


class ProdHttpDeliveryAdapter:
    """Stub for signed remote HTTP delivery (OX-10-004)."""

    def __init__(self) -> None:
        raise NotImplementedError(
            "ProdHttpDeliveryAdapter is not implemented yet. "
            "See specs/outbox.yaml OX-10-004."
        )
