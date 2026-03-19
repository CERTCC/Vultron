"""Per-semantic inbound domain event type for unrecognized activities."""

from typing import Literal

from vultron.core.models.events.base import MessageSemantics, VultronEvent


class UnknownReceivedEvent(VultronEvent):
    """Activity did not match any known semantic pattern."""

    semantic_type: Literal[MessageSemantics.UNKNOWN] = MessageSemantics.UNKNOWN
