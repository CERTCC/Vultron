"""Use case for unknown/unrecognized activities."""

import logging

from vultron.core.models.dead_letter import DeadLetterRecord
from vultron.core.models.events.unknown import (
    UnknownReceivedEvent,
    UnresolvableObjectReceivedEvent,
)
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


class UnresolvableObjectUseCase:
    """Stores a dead-letter record for activities whose object_ URI could not
    be resolved after rehydration.

    See ``specs/semantic-extraction.md`` SE-04-002, SE-04-003.
    """

    def __init__(
        self, dl: DataLayer, request: UnresolvableObjectReceivedEvent
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> None:
        request = self._request
        unresolvable_uri = request.object_id or ""
        logger.warning(
            "Unresolvable object_ URI '%s' in activity '%s' (actor '%s'); "
            "storing dead-letter record.",
            unresolvable_uri,
            request.activity_id,
            request.actor_id,
        )
        activity_summary = (
            request.activity.model_dump(by_alias=True, exclude_none=True)
            if request.activity is not None
            else None
        )
        record = DeadLetterRecord(
            unresolvable_uri=unresolvable_uri,
            actor_id=request.actor_id,
            activity_id=request.activity_id,
            activity_type=request.activity_type,
            activity_summary=activity_summary,
        )
        self._dl.save(record)
