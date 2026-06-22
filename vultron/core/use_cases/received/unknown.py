"""Use case for unknown/unrecognized activities."""

import logging

from vultron.core.models.events.unknown import (
    UnknownReceivedEvent,
    UnresolvableObjectReceivedEvent,
)
from vultron.core.ports.case_persistence import CasePersistence

logger = logging.getLogger(__name__)


class UnknownUseCase:
    """Logs a warning for any activity that could not be matched to a known
    semantic type.
    """

    def __init__(
        self, dl: CasePersistence, request: UnknownReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: UnknownReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.warning("unknown use case called for event: %s", request)


class UnresolvableObjectUseCase:
    """Stores a dead-letter record for activities whose object_ URI could not
    be resolved after rehydration.

    See ``specs/semantic-extraction.yaml`` SE-04-002, SE-04-003.
    """

    def __init__(
        self, dl: CasePersistence, request: UnresolvableObjectReceivedEvent
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> None:
        from py_trees.common import Status

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.inbox.dead_letter_tree import (
            create_store_dead_letter_tree,
        )

        request = self._request
        unresolvable_uri = request.object_id or ""
        logger.warning(
            "Unresolvable object_ URI '%s' in activity '%s' (actor '%s'); "
            "storing dead-letter record.",
            unresolvable_uri,
            request.activity_id,
            request.actor_id,
        )
        tree = create_store_dead_letter_tree(request=request)
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=request.actor_id,
            activity=request,
        )
        if result.status != Status.SUCCESS:
            logger.warning(
                "StoreDeadLetterBT did not succeed for activity '%s': %s",
                request.activity_id,
                BTBridge.get_failure_reason(tree),
            )
