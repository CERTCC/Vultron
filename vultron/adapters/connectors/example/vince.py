"""
VINCE connector plugin — example stub.

Illustrates how a ``ConnectorPlugin`` implementation translates between
VINCE (Vulnerability Information and Coordination Environment) platform
events and Vultron domain events.

Typical mappings (not yet implemented):

- VINCE case created        → Vultron ``create_case`` use case
- VINCE vendor contacted    → Vultron ``invite_actor_to_case`` use case
- VINCE disclosure published → Vultron ``announce_embargo_event_to_case`` use case

See ``vultron/adapters/connectors/base.py`` for the ``ConnectorPlugin``
Protocol this module must satisfy.
"""

from vultron.adapters.connectors.base import ConnectorPlugin


class VinceConnector:
    """Example VINCE connector — not yet implemented."""

    name = "vince"

    def on_inbound_event(self, event: object) -> None:
        raise NotImplementedError

    def on_outbound_event(self, event: object) -> None:
        raise NotImplementedError


assert isinstance(VinceConnector(), ConnectorPlugin)
