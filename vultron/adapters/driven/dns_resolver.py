"""
DNS resolver driven adapter — stub.

Concrete implementation of the ``core/ports/dns_resolver.py`` port
interface for DNS TXT-based actor/instance trust discovery.

Future implementation will perform DNS TXT lookups to resolve Vultron
instance metadata (public keys, inbox URLs, supported protocol versions)
following the WebFinger / NodeInfo conventions used by ActivityPub
implementations.

This adapter is optional and will only be wired in when DNS-based trust
discovery is required.
"""
