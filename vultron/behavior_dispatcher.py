"""
Provides a behavior dispatcher for Vultron
"""

import logging
from typing import TYPE_CHECKING, Any, Protocol

from vultron.dispatcher_errors import VultronApiHandlerNotFoundError
from vultron.core.models.events import InboundPayload, MessageSemantics
from vultron.wire.as2.extractor import find_matching_semantics
from vultron.types import BehaviorHandler, DispatchActivity

if TYPE_CHECKING:
    from vultron.api.v2.datalayer.abc import DataLayer

logger = logging.getLogger(__name__)


def prepare_for_dispatch(activity: Any) -> DispatchActivity:
    """
    Prepares an activity for dispatch by extracting its message semantics and packaging it into a DispatchActivity.
    """
    logger.debug(
        f"Preparing activity '{activity.as_id}' of type '{activity.as_type}' for dispatch."
    )

    # We want dispatching to be simple and fast, so we only need to extract enough information
    # to decide how to route the message. Any additional extraction can be downstream of the dispatcher.

    actor_id = str(activity.actor) if activity.actor else ""
    obj = getattr(activity, "as_object", None)
    object_id = getattr(obj, "as_id", None) if obj is not None else None
    object_type = (
        str(getattr(obj, "as_type", None)) if obj is not None else None
    )

    payload = InboundPayload(
        activity_id=activity.as_id,
        actor_id=actor_id,
        object_type=object_type,
        object_id=object_id,
        raw_activity=activity,
    )
    data = {
        "semantic_type": find_matching_semantics(activity=activity),
        "activity_id": activity.as_id,
        "payload": payload,
    }

    dispatch_msg = DispatchActivity(**data)
    logger.debug(
        f"Prepared dispatch message with semantics '{dispatch_msg.semantic_type}' for activity '{dispatch_msg.payload.activity_id}'"
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

    def __init__(
        self, handler_map: dict | None = None, dl: "DataLayer | None" = None
    ):
        if handler_map is None:
            from vultron.api.v2.backend.handler_map import SEMANTICS_HANDLERS

            handler_map = SEMANTICS_HANDLERS
        self._handler_map = handler_map
        self.dl = dl

    def dispatch(self, dispatchable: DispatchActivity) -> None:
        activity = dispatchable.payload.raw_activity
        semantic_type = dispatchable.semantic_type

        logger.info(
            f"Dispatching activity of type '{dispatchable.payload.object_type}' with semantics '{semantic_type}'"
        )
        logger.debug(f"Activity payload: {activity.model_dump_json(indent=2)}")
        self._handle(dispatchable)

    def _handle(self, dispatchable: DispatchActivity) -> None:
        """
        Internal method to route the dispatchable activity to the correct handler based on its semantics.
        """
        handler: BehaviorHandler = self._get_handler_for_semantics(
            dispatchable.semantic_type
        )
        handler(dispatchable=dispatchable, dl=self.dl)

    def _get_handler_for_semantics(
        self, semantics: MessageSemantics
    ) -> BehaviorHandler:
        """
        Retrieves the handler function for the given message semantics from the SEMANTICS_HANDLERS mapping.
        Override this method if you want to implement a different way of mapping semantics to handlers
        (e.g. using a database or external service).
        """
        handler_func = self._handler_map.get(semantics, None)

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

    pass


def get_dispatcher(handler_map=None, dl=None) -> ActivityDispatcher:
    """
    Factory function to get an instance of the ActivityDispatcher.
    This allows for flexibility in swapping out different dispatcher implementations if needed.
    """
    return DirectActivityDispatcher(handler_map=handler_map, dl=dl)
