"""
Jira connector plugin — example stub.

Illustrates how a ``ConnectorPlugin`` implementation translates between
Jira issue/comment events and Vultron domain events.

Typical mappings (not yet implemented):

- Jira issue created  → Vultron ``create_report`` use case
- Jira comment added  → Vultron ``add_note_to_case`` use case
- Vultron case closed → Jira issue resolved (via Jira REST API)

See ``vultron/adapters/connectors/base.py`` for the ``ConnectorPlugin``
Protocol this module must satisfy.
"""

from vultron.adapters.connectors.base import ConnectorPlugin


class JiraConnector:
    """Example Jira connector — not yet implemented."""

    name = "jira"

    def on_inbound_event(self, event: object) -> None:
        raise NotImplementedError

    def on_outbound_event(self, event: object) -> None:
        raise NotImplementedError


assert isinstance(JiraConnector(), ConnectorPlugin)
