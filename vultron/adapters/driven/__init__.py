"""
Driven adapters (right-side / secondary adapters).

These adapters implement the port interfaces defined in ``core/ports/`` so
that the core can call out to external systems without being coupled to
them. The core defines the interface; this package provides the
implementation.

Modules:

- ``datalayer.py``  — Concrete activity persistence (e.g., TinyDB).
- ``demo_http_delivery.py`` — Unsigned HTTP transport for outbound
                           ActivityStreams payloads; receives serialized
                           AS2 from the wire layer.
- ``prod_http_delivery.py`` — Stub implementation for future signed remote
                           delivery; raises ``NotImplementedError`` when
                           instantiated (OX-10-004).

"""
