"""Use case for unknown/unrecognized activities."""

import logging

from vultron.core.models.events.unknown import UnknownReceivedEvent
from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


class UnknownUseCase:
    """Logs a warning for any activity that could not be matched to a known
    semantic type.
    """

    def __init__(self, dl: DataLayer, request: UnknownReceivedEvent) -> None:
        self._dl = dl
        self._request: UnknownReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.warning("unknown use case called for event: %s", request)
