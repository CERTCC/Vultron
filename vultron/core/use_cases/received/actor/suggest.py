"""Use cases for CaseActor-routed actor-suggestion activities (ADR-0026)."""

import logging
from typing import TYPE_CHECKING

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.suggest_actor_tree import (
    create_recommend_actor_to_case_received_tree,
)
from vultron.core.models.events.actor import (
    OfferActorToCaseReceivedEvent,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases.received.sync import _find_local_actor_id

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class OfferActorToCaseReceivedUseCase:
    """CaseActor received Offer(Actor, Case) from a recommending participant.

    Delegates to :func:`create_recommend_actor_to_case_received_tree` via
    BTBridge to commit the ledger entry and DM Offer(CaseParticipant) to the
    Case Owner (CM-16-002..004, ADR-0026).
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: OfferActorToCaseReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> None:
        request = self._request
        activity_id = request.activity_id
        recommender_id = request.actor_id
        case_id = request.target_id
        # Offer(Actor, Case): object_ is an as_Actor; object_id is the actor URI directly.
        recommended_id = request.object_id

        if not recommended_id or not case_id:
            logger.warning(
                "OfferActorToCaseReceived: missing recommended_id or case_id"
                " in event '%s' — skipping",
                activity_id,
            )
            return

        local_actor_id = _find_local_actor_id(self._dl)
        if local_actor_id is None:
            logger.warning(
                "OfferActorToCaseReceived: no local actor found in DataLayer"
                " — skipping event '%s'",
                activity_id,
            )
            return

        tree = create_recommend_actor_to_case_received_tree(
            recommendation_id=activity_id,
            recommender_id=recommender_id,
            recommended_id=recommended_id,
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl, trigger_activity=self._trigger_activity
        )
        bridge.execute_with_setup(
            tree, actor_id=local_actor_id, activity=request
        )
