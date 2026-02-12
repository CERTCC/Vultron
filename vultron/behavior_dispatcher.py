"""
Provides a behavior dispatcher for Vultron
"""

from typing import Protocol

from pydantic import BaseModel

from vultron.api.v2.backend.handlers import BehaviorHandler
from vultron.api.v2.errors import VultronApiHandlerNotFoundError
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.enums import MessageSemantics
from vultron.semantic_handler_map import SEMANTICS_HANDLERS
from vultron.semantic_map import find_matching_semantics
import logging

logger = logging.getLogger(__name__)


class DispatchActivity(BaseModel):
    """
    Data model to represent a dispatchable activity with its associated message semantics as a header.
    """

    semantic_type: MessageSemantics
    activity_id: str
    payload: as_Activity
    # We are deliberately not including case_id or report_id here because
    # where they are located in the payload can vary depending on message semantics.
    # Therefore it is better to leave it to downstream semantic-specific _old_handlers to
    # extract those values for logging or other purposes rather than having to build
    # a parallel extraction logic here in the dispatcher that may not be universally applicable.


def prepare_for_dispatch(activity: as_Activity) -> DispatchActivity:
    """
    Prepares an activity for dispatch by extracting its message semantics and packaging it into a DispatchActivity.
    """
    logger.debug(
        f"Preparing activity '{activity.as_id}' of type '{activity.as_type}' for dispatch."
    )

    # We want dispatching to be simple and fast, so we only need to extract enough information
    # to decide how to route the message. Any additional extraction can be downstream of the dispatcher.

    data = {
        "semantic_type": find_matching_semantics(activity=activity),
        "activity_id": activity.as_id,
        "payload": activity,
    }

    dispatch_msg = DispatchActivity(**data)
    logger.debug(
        f"Prepared dispatch message with semantics '{dispatch_msg.semantic_type}' for activity '{dispatch_msg.payload.as_id}'"
    )
    return dispatch_msg


class ActivityDispatcher(Protocol):
    """
    Protocol for dispatching activities to their corresponding _old_handlers based on message semantics.
    """

    def dispatch(self, dispatchable: DispatchActivity) -> None:
        """Dispatches an activity to the appropriate handler based on its semantic type."""
        ...


class DispatcherBase(ActivityDispatcher):
    """
    Base class for ActivityDispatcher implementations. Can include shared logic or utilities for dispatching.
    """

    def dispatch(self, dispatchable: DispatchActivity) -> None:
        activity = dispatchable.payload
        semantic_type = dispatchable.semantic_type

        logger.info(
            f"Dispatching activity of type '{activity.as_type}' with semantics '{semantic_type}'"
        )
        self._handle(dispatchable)

    def _handle(self, dispatchable: DispatchActivity) -> None:
        """
        Internal method to route the dispatchable activity to the correct handler based on its semantics.
        """
        handler: BehaviorHandler = self._get_handler_for_semantics(
            dispatchable.semantic_type
        )
        handler(dispatchable=dispatchable)

    def _get_handler_for_semantics(
        self, semantics: MessageSemantics
    ) -> BehaviorHandler:
        """
        Retrieves the handler function for the given message semantics from the SEMANTICS_HANDLERS mapping.
        Override this method if you want to implement a different way of mapping semantics to handlers
        (e.g. using a database or external service).
        """
        handler_func = SEMANTICS_HANDLERS.get(semantics, None)

        if handler_func is None:
            logger.error(f"No handler found for semantics '{semantics}'")
            raise VultronApiHandlerNotFoundError(
                f"No handler found for semantics '{semantics}'"
            )

        return handler_func


class DirectActivityDispatcher(DispatcherBase):
    """
    A local implementation of the ActivityDispatcher protocol.
    """


def get_dispatcher() -> ActivityDispatcher:
    """
    Factory function to get an instance of the ActivityDispatcher.
    This allows for flexibility in swapping out different dispatcher implementations if needed.
    """
    return DirectActivityDispatcher()
