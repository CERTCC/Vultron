"""Use case for unknown/unrecognized activities."""

import logging

from vultron.core.models.events.unknown import UnknownReceivedEvent
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.use_case import UseCase

logger = logging.getLogger(__name__)


class UnknownUseCase(UseCase[UnknownReceivedEvent, None]):
    """Reference implementation of ``UseCase[UnknownReceivedEvent, None]``.

    Logs a warning for any activity that could not be matched to a known
    semantic type.  Intended as the canonical example of the class-based use
    case interface introduced in P75-4-pre.
    """

    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(self, request: UnknownReceivedEvent) -> None:
        logger.warning("unknown use case called for event: %s", request)
