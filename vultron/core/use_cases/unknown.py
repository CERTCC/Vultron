"""Use case for unknown/unrecognized activities."""

import logging

from vultron.core.models.events.unknown import UnknownReceivedEvent
from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


def unknown(event: UnknownReceivedEvent, dl: DataLayer) -> None:
    logger.warning("unknown use case called for event: %s", event)
