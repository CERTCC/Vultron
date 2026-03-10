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
