"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import TYPE_CHECKING

from vultron.core.models.events.actor import (
    AcceptSuggestActorToCaseReceivedEvent,
    RejectSuggestActorToCaseReceivedEvent,
    SuggestActorToCaseReceivedEvent,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import _idempotent_create

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class SuggestActorToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: SuggestActorToCaseReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: SuggestActorToCaseReceivedEvent = request
        self._trigger_activity = trigger_activity

    def execute(self) -> None:
        request = self._request
        activity_id = request.activity_id
        recommender_id = request.actor_id
        invitee_id = request.object_id
        case_id = request.target_id

        if not invitee_id or not case_id:
            logger.warning(
                "SuggestActorToCaseReceived: missing invitee_id or case_id"
                " in event '%s' — skipping",
                activity_id,
            )
            return

        # Persist the incoming recommendation for record-keeping.
        _idempotent_create(
            self._dl,
            request.activity_type,
            activity_id,
            request.activity,
            "RecommendActor",
            activity_id,
        )

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.case.suggest_actor_tree import (
            create_suggest_actor_tree,
        )
        from vultron.core.use_cases.received.sync import _find_local_actor_id

        local_actor_id = _find_local_actor_id(self._dl)
        if local_actor_id is None:
            logger.warning(
                "SuggestActorToCaseReceived: no local actor found in DataLayer"
                " — skipping event '%s'",
                activity_id,
            )
            return

        tree = create_suggest_actor_tree(
            recommendation_id=activity_id,
            recommender_id=recommender_id,
            invitee_id=invitee_id,
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl, trigger_activity=self._trigger_activity
        )
        bridge.execute_with_setup(tree, actor_id=local_actor_id)


class AcceptSuggestActorToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: AcceptSuggestActorToCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: AcceptSuggestActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.activity_type,
            request.activity_id,
            request.activity,
            "AcceptSuggestActorToCase",
            request.activity_id,
        )


class RejectSuggestActorToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: RejectSuggestActorToCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: RejectSuggestActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.info(
            "Actor '%s' rejected recommendation to add actor '%s' to case",
            request.actor_id,
            request.suggested_actor_id,
        )
