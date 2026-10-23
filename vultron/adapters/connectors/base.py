"""
ConnectorPlugin Protocol — base interface for bidirectional connector adapters.

A connector translates between an external system's events and Vultron domain
events. Connectors differ from pure driving or driven adapters in that they
may both receive events from and push events to an external system (e.g., an
issue tracker, mailing list, or vulnerability database).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ConnectorPlugin(Protocol):
    """
    Interface that all Vultron connector plugins must satisfy.

    Plugins are discovered via Python entry points under the
    ``vultron.connectors`` group (see ``loader.py``).
    """

    #: Human-readable name used in logs and configuration.
    name: str

    def on_inbound_event(self, event: object) -> None:
        """
        Called when the external system emits an event that should be
        translated into a Vultron domain event and forwarded to the core.

        ``event`` is the raw external payload — the connector is responsible
        for validating and translating it before calling a core use case.
        """

    def on_outbound_event(self, event: object) -> None:
        """
        Called when a Vultron domain event should be forwarded to the
        external system.

        ``event`` is a serialized domain event — the connector is responsible
        for translating it into the external system's format and delivering it.
        """
