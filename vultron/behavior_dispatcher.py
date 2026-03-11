"""
Provides a behavior dispatcher for Vultron
"""

import logging
from typing import TYPE_CHECKING, Protocol

from vultron.dispatcher_errors import VultronApiHandlerNotFoundError
from vultron.core.models.events import MessageSemantics
from vultron.types import BehaviorHandler, DispatchActivity

if TYPE_CHECKING:
    from vultron.core.ports.activity_store import DataLayer

logger = logging.getLogger(__name__)


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

    def __init__(self, handler_map: dict, dl: "DataLayer | None" = None):
        self._handler_map = handler_map
        self.dl = dl

    def dispatch(self, dispatchable: DispatchActivity) -> None:
        semantic_type = dispatchable.semantic_type

        logger.info(
            f"Dispatching activity of type '{dispatchable.payload.object_type}' with semantics '{semantic_type}'"
        )
        logger.debug(
            f"Activity payload: activity_id={dispatchable.payload.activity_id} "
            f"actor_id={dispatchable.payload.actor_id} "
            f"object_type={dispatchable.payload.object_type}"
        )
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


def get_dispatcher(
    handler_map: dict, dl: "DataLayer | None" = None
) -> ActivityDispatcher:
    """
    Factory function to get an instance of the ActivityDispatcher.
    This allows for flexibility in swapping out different dispatcher implementations if needed.
    """
    return DirectActivityDispatcher(handler_map=handler_map, dl=dl)
