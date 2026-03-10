"""
Driven adapters (right-side / secondary adapters).

These adapters implement the port interfaces defined in ``core/ports/`` so
that the core can call out to external systems without being coupled to
them. The core defines the interface; this package provides the
implementation.

Modules:

- ``activity_store.py``  — Concrete activity persistence (e.g., TinyDB).
- ``delivery_queue.py``  — Outbound activity queue implementation.
- ``http_delivery.py``   — HTTP transport for outbound ActivityStreams
                           payloads (transport only — receives serialized
                           AS2 from the wire layer).
- ``dns_resolver.py``    — Optional DNS TXT lookup for trust discovery.
"""
