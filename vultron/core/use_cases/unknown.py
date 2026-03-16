"""Use case for unknown/unrecognized activities."""

import logging

from vultron.core.models.events.unknown import UnknownReceivedEvent
from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


class UnknownUseCase:
    """Reference implementation of ``UseCase[UnknownReceivedEvent, None]``.

    Logs a warning for any activity that could not be matched to a known
    semantic type.  Intended as the canonical example of the class-based use
    case interface introduced in P75-4-pre.
    """

    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(self, request: UnknownReceivedEvent) -> None:
        logger.warning("unknown use case called for event: %s", request)


def unknown(event: UnknownReceivedEvent, dl: DataLayer) -> None:
    """Backward-compatible callable wrapper used by the current dispatcher.

    Delegates to ``UnknownUseCase`` so the class remains the single source
    of logic while the routing table continues to hold plain callables until
    P75-4 migrates all use cases to the class interface.
    """
    UnknownUseCase(dl).execute(event)
