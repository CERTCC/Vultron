"""
Driven adapters (right-side / secondary adapters).

These adapters implement the port interfaces defined in ``core/ports/`` so
that the core can call out to external systems without being coupled to
them. The core defines the interface; this package provides the
implementation.

Modules:

- ``datalayer.py``  — Concrete activity persistence (e.g., TinyDB).
- ``http_delivery.py``   — HTTP transport for outbound ActivityStreams
                           payloads (transport only — receives serialized
                           AS2 from the wire layer).

"""
