"""Use cases for CaseActor-routed actor-suggestion activities (ADR-0026)."""

import logging
from typing import TYPE_CHECKING

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.suggest_actor_tree import (
    create_accept_actor_recommendation_received_tree,
    create_recommend_actor_to_case_received_tree,
    create_reject_actor_recommendation_received_tree,
)
from vultron.core.models.events.actor import (
    AcceptActorRecommendationReceivedEvent,
    OfferActorToCaseReceivedEvent,
    RejectActorRecommendationReceivedEvent,
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
        # The event's object is a CaseParticipant; extract the actual actor ID
        # from its attributed_to field (object_id has the #participant suffix).
        participant_obj = getattr(request.activity, "object_", None)
        raw_recommended = getattr(participant_obj, "attributed_to", None)
        recommended_id = (
            getattr(raw_recommended, "id_", None) or request.object_id
        )

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


class AcceptActorRecommendationReceivedUseCase:
    """CaseActor received Accept(Offer(CaseParticipant)) from the Case Owner.

    Delegates to :func:`create_accept_actor_recommendation_received_tree` via
    BTBridge to commit the ledger entry, notify the recommender, and invite the
    recommended actor (CM-16-006, ADR-0026).
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: AcceptActorRecommendationReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> None:
        request = self._request
        activity_id = request.activity_id
        case_id = request.target_id
        # The Accept wraps Offer(CaseParticipant); the Offer's `object_` is the
        # CaseParticipant, whose `attributed_to` is the recommended actor.
        # The Offer's `origin` carries the original recommender Offer ID.
        inner_offer = getattr(request.activity, "object_", None)
        participant_obj = getattr(inner_offer, "object_", None)
        raw_invitee = getattr(participant_obj, "attributed_to", None)
        invitee_id = getattr(raw_invitee, "id_", raw_invitee)
        recommendation_id = getattr(inner_offer, "origin", None)
        recommender_id = None
        if recommendation_id:
            stored_offer = self._dl.read(recommendation_id)
            if stored_offer is not None:
                raw_actor = getattr(stored_offer, "actor", None)
                recommender_id = getattr(raw_actor, "id_", raw_actor)

        if not case_id or not invitee_id:
            logger.warning(
                "AcceptActorRecommendationReceived: missing case_id or"
                " invitee_id in event '%s' — skipping",
                activity_id,
            )
            return

        local_actor_id = _find_local_actor_id(self._dl)
        if local_actor_id is None:
            logger.warning(
                "AcceptActorRecommendationReceived: no local actor found"
                " — skipping event '%s'",
                activity_id,
            )
            return

        tree = create_accept_actor_recommendation_received_tree(
            accept_id=activity_id,
            accept_obj=request.activity,
            recommendation_id=recommendation_id or "",
            recommender_id=recommender_id or "",
            invitee_id=invitee_id,
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl, trigger_activity=self._trigger_activity
        )
        bridge.execute_with_setup(
            tree, actor_id=local_actor_id, activity=request
        )


class RejectActorRecommendationReceivedUseCase:
    """CaseActor received Reject(Offer(CaseParticipant)) from the Case Owner.

    Delegates to :func:`create_reject_actor_recommendation_received_tree` via
    BTBridge to commit the ledger entry and notify the original recommender
    (CM-16-007, ADR-0026).
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: RejectActorRecommendationReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> None:
        request = self._request
        activity_id = request.activity_id
        case_id = request.target_id
        inner_offer = getattr(request.activity, "object_", None)
        participant_obj = getattr(inner_offer, "object_", None)
        raw_invitee = getattr(participant_obj, "attributed_to", None)
        recommended_id = getattr(raw_invitee, "id_", None) or request.object_id
        recommendation_id = getattr(inner_offer, "origin", None)
        recommender_id = None
        if recommendation_id:
            stored_offer = self._dl.read(recommendation_id)
            if stored_offer is not None:
                raw_actor = getattr(stored_offer, "actor", None)
                recommender_id = getattr(raw_actor, "id_", raw_actor)

        if not case_id:
            logger.warning(
                "RejectActorRecommendationReceived: missing case_id in"
                " event '%s' — skipping",
                activity_id,
            )
            return

        local_actor_id = _find_local_actor_id(self._dl)
        if local_actor_id is None:
            logger.warning(
                "RejectActorRecommendationReceived: no local actor found"
                " — skipping event '%s'",
                activity_id,
            )
            return

        tree = create_reject_actor_recommendation_received_tree(
            reject_id=activity_id,
            reject_obj=request.activity,
            recommendation_id=recommendation_id or "",
            recommender_id=recommender_id or "",
            recommended_id=recommended_id or "",
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl, trigger_activity=self._trigger_activity
        )
        bridge.execute_with_setup(
            tree, actor_id=local_actor_id, activity=request
        )
