"""
Handler functions for case actor/participant invitation and suggestion activities.
"""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.types import DispatchActivity

from vultron.api.v2.datalayer.abc import DataLayer

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.SUGGEST_ACTOR_TO_CASE)
def suggest_actor_to_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process a RecommendActor (Offer(object=Actor, target=Case)) activity.

    This arrives in the *case owner's* inbox. The handler persists the
    recommendation so the case owner can later accept or reject it.
    Idempotent: if the recommendation is already stored, skips.

    Args:
        dispatchable: DispatchActivity containing the RecommendActor
    """
    payload = dispatchable.payload

    try:
        existing = dl.get(payload.activity_type, payload.activity_id)
        if existing is not None:
            logger.info(
                "RecommendActor '%s' already stored — skipping (idempotent)",
                payload.activity_id,
            )
            return None

        dl.create(dispatchable.wire_activity)
        logger.info(
            "Stored actor recommendation '%s' (actor=%s, object=%s, target=%s)",
            payload.activity_id,
            payload.actor_id,
            payload.object_id,
            payload.target_id,
        )

    except Exception as e:
        logger.error(
            "Error in suggest_actor_to_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE)
def accept_suggest_actor_to_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process an AcceptActorRecommendation (Accept(object=RecommendActor)) activity.

    This arrives in the *recommending actor's* inbox after the case owner
    accepts. The handler logs the acceptance and persists it. The actual
    invitation of the accepted actor is a separate step by the case owner.
    Idempotent: if already stored, skips.

    Args:
        dispatchable: DispatchActivity containing the AcceptActorRecommendation
    """
    payload = dispatchable.payload

    try:
        existing = dl.get(payload.activity_type, payload.activity_id)
        if existing is not None:
            logger.info(
                "AcceptActorRecommendation '%s' already stored — skipping (idempotent)",
                payload.activity_id,
            )
            return None

        dl.create(dispatchable.wire_activity)
        logger.info(
            "Stored acceptance of actor recommendation '%s' (actor=%s, object=%s, target=%s)",
            payload.activity_id,
            payload.actor_id,
            payload.object_id,
            payload.target_id,
        )

    except Exception as e:
        logger.error(
            "Error in accept_suggest_actor_to_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE)
def reject_suggest_actor_to_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process a RejectActorRecommendation (Reject(object=RecommendActor)) activity.

    This arrives in the *recommending actor's* inbox after the case owner
    rejects the recommendation. No state change is required.

    Args:
        dispatchable: DispatchActivity containing the RejectActorRecommendation
    """
    payload = dispatchable.payload

    try:
        logger.info(
            "Actor '%s' rejected recommendation to add actor '%s' to case",
            payload.actor_id,
            payload.object_id,
        )

    except Exception as e:
        logger.error(
            "Error in reject_suggest_actor_to_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER)
def offer_case_ownership_transfer(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process an OfferCaseOwnershipTransfer (Offer(object=Case, target=Actor)) activity.

    This arrives in the *proposed new owner's* inbox. The handler persists
    the offer so the target can later accept or reject it.
    Idempotent: if the offer is already stored, skips.

    Args:
        dispatchable: DispatchActivity containing the OfferCaseOwnershipTransfer
    """
    payload = dispatchable.payload

    try:
        existing = dl.get(payload.activity_type, payload.activity_id)
        if existing is not None:
            logger.info(
                "OfferCaseOwnershipTransfer '%s' already stored — skipping (idempotent)",
                payload.activity_id,
            )
            return None

        dl.create(dispatchable.wire_activity)
        logger.info(
            "Stored ownership transfer offer '%s' (actor=%s, target=%s)",
            payload.activity_id,
            payload.actor_id,
            payload.target_id,
        )

    except Exception as e:
        logger.error(
            "Error in offer_case_ownership_transfer for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER)
def accept_case_ownership_transfer(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process an AcceptCaseOwnershipTransfer (Accept(object=OfferCaseOwnershipTransfer)) activity.

    This arrives in the *current owner's* inbox after the proposed new owner
    accepts. The handler rehydrates the offer to retrieve the case, then
    updates the case's attributed_to field to the new owner.
    Idempotent: if the case already belongs to the new owner, skips.

    Args:
        dispatchable: DispatchActivity containing the AcceptCaseOwnershipTransfer
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.db_record import object_to_record

    payload = dispatchable.payload

    try:
        case = rehydrate(payload.inner_object_id)
        new_owner_id = payload.actor_id
        case_id = payload.inner_object_id

        current_owner_id = (
            case.attributed_to.as_id
            if hasattr(case.attributed_to, "as_id")
            else str(case.attributed_to) if case.attributed_to else None
        )
        if current_owner_id == new_owner_id:
            logger.info(
                "Case '%s' already owned by '%s' — skipping (idempotent)",
                case_id,
                new_owner_id,
            )
            return None

        case.attributed_to = new_owner_id
        dl.update(case_id, object_to_record(case))
        logger.info(
            "Transferred ownership of case '%s' from '%s' to '%s'",
            case_id,
            current_owner_id,
            new_owner_id,
        )

    except Exception as e:
        logger.error(
            "Error in accept_case_ownership_transfer for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER)
def reject_case_ownership_transfer(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process a RejectCaseOwnershipTransfer (Reject(object=OfferCaseOwnershipTransfer)) activity.

    This arrives in the *current owner's* inbox after the proposed new owner
    rejects. Case ownership is unchanged. No state change required.

    Args:
        dispatchable: DispatchActivity containing the RejectCaseOwnershipTransfer
    """
    payload = dispatchable.payload

    try:
        logger.info(
            "Actor '%s' rejected ownership transfer offer '%s' — ownership unchanged",
            payload.actor_id,
            payload.object_id,
        )

    except Exception as e:
        logger.error(
            "Error in reject_case_ownership_transfer for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.INVITE_ACTOR_TO_CASE)
def invite_actor_to_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process an Invite(actor=CaseOwner, object=Actor, target=Case) activity.

    This arrives in the *invited actor's* inbox. The handler persists the
    Invite so that the actor can later accept or reject it.

    Args:
        dispatchable: DispatchActivity containing the RmInviteToCase activity
    """
    payload = dispatchable.payload

    try:
        existing = dl.get(payload.activity_type, payload.activity_id)
        if existing is not None:
            logger.info(
                "Invite '%s' already stored — skipping (idempotent)",
                payload.activity_id,
            )
            return None

        dl.create(dispatchable.wire_activity)
        logger.info(
            "Stored invite '%s' (actor=%s, target=%s)",
            payload.activity_id,
            payload.actor_id,
            payload.target_id,
        )

    except Exception as e:
        logger.error(
            "Error in invite_actor_to_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE)
def accept_invite_actor_to_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process an Accept(object=RmInviteToCase) activity.

    This arrives in the *case owner's* inbox after the invited actor accepts.
    The handler creates a CaseParticipant for the invited actor and adds them
    to the case's participant list. Idempotent: if the participant is already
    in the case, the handler returns without side effects (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the RmAcceptInviteToCase
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.db_record import object_to_record
    from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant

    payload = dispatchable.payload

    try:
        case = rehydrate(payload.inner_target_id)
        invitee_id = payload.inner_object_id
        case_id = payload.inner_target_id

        existing_ids = [
            (p.as_id if hasattr(p, "as_id") else p)
            for p in case.case_participants
        ]
        if (
            invitee_id in case.actor_participant_index
            or invitee_id in existing_ids
        ):
            logger.info(
                "Actor '%s' already participant in case '%s' — skipping (idempotent)",
                invitee_id,
                case_id,
            )
            return None

        active_embargo_id = (
            case.active_embargo.as_id
            if hasattr(case.active_embargo, "as_id")
            else (
                str(case.active_embargo)
                if case.active_embargo is not None
                else None
            )
        )

        participant = CaseParticipant(
            id=f"{case_id}/participants/{invitee_id.split('/')[-1]}",
            attributed_to=invitee_id,
            context=case_id,
        )
        if active_embargo_id:
            participant.accepted_embargo_ids.append(active_embargo_id)
        dl.create(participant)

        case.add_participant(participant)
        case.record_event(invitee_id, "participant_joined")
        if active_embargo_id:
            case.record_event(active_embargo_id, "embargo_accepted")
        dl.update(case_id, object_to_record(case))

        logger.info(
            "Added participant '%s' to case '%s' via accepted invite",
            invitee_id,
            case_id,
        )

    except Exception as e:
        logger.error(
            "Error in accept_invite_actor_to_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE)
def reject_invite_actor_to_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process a Reject(object=RmInviteToCase) activity.

    This arrives in the *case owner's* inbox. The handler logs the rejection;
    no state change is required.

    Args:
        dispatchable: DispatchActivity containing the RmRejectInviteToCase
    """
    payload = dispatchable.payload

    try:
        logger.info(
            "Actor '%s' rejected invitation '%s'",
            payload.actor_id,
            payload.object_id,
        )

    except Exception as e:
        logger.error(
            "Error in reject_invite_actor_to_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )
