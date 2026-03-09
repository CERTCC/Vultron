"""
Handler functions for case actor/participant invitation and suggestion activities.
"""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.types import DispatchActivity

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.SUGGEST_ACTOR_TO_CASE)
def suggest_actor_to_case(dispatchable: DispatchActivity) -> None:
    """
    Process a RecommendActor (Offer(object=Actor, target=Case)) activity.

    This arrives in the *case owner's* inbox. The handler persists the
    recommendation so the case owner can later accept or reject it.
    Idempotent: if the recommendation is already stored, skips.

    Args:
        dispatchable: DispatchActivity containing the RecommendActor
    """
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload.raw_activity

    try:
        dl = get_datalayer()
        existing = dl.get(activity.as_type.value, activity.as_id)
        if existing is not None:
            logger.info(
                "RecommendActor '%s' already stored — skipping (idempotent)",
                activity.as_id,
            )
            return None

        dl.create(activity)
        logger.info(
            "Stored actor recommendation '%s' (actor=%s, object=%s, target=%s)",
            activity.as_id,
            activity.actor,
            activity.as_object,
            activity.target,
        )

    except Exception as e:
        logger.error(
            "Error in suggest_actor_to_case for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE)
def accept_suggest_actor_to_case(dispatchable: DispatchActivity) -> None:
    """
    Process an AcceptActorRecommendation (Accept(object=RecommendActor)) activity.

    This arrives in the *recommending actor's* inbox after the case owner
    accepts. The handler logs the acceptance and persists it. The actual
    invitation of the accepted actor is a separate step by the case owner.
    Idempotent: if already stored, skips.

    Args:
        dispatchable: DispatchActivity containing the AcceptActorRecommendation
    """
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload.raw_activity

    try:
        dl = get_datalayer()
        existing = dl.get(activity.as_type.value, activity.as_id)
        if existing is not None:
            logger.info(
                "AcceptActorRecommendation '%s' already stored — skipping (idempotent)",
                activity.as_id,
            )
            return None

        dl.create(activity)
        logger.info(
            "Stored acceptance of actor recommendation '%s' (actor=%s, object=%s, target=%s)",
            activity.as_id,
            activity.actor,
            activity.as_object,
            activity.target,
        )

    except Exception as e:
        logger.error(
            "Error in accept_suggest_actor_to_case for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE)
def reject_suggest_actor_to_case(dispatchable: DispatchActivity) -> None:
    """
    Process a RejectActorRecommendation (Reject(object=RecommendActor)) activity.

    This arrives in the *recommending actor's* inbox after the case owner
    rejects the recommendation. No state change is required.

    Args:
        dispatchable: DispatchActivity containing the RejectActorRecommendation
    """
    activity = dispatchable.payload.raw_activity

    try:
        object_ref = activity.as_object
        object_id = (
            object_ref.as_id
            if hasattr(object_ref, "as_id")
            else str(object_ref)
        )
        logger.info(
            "Actor '%s' rejected recommendation to add actor '%s' to case",
            activity.actor,
            object_id,
        )

    except Exception as e:
        logger.error(
            "Error in reject_suggest_actor_to_case for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER)
def offer_case_ownership_transfer(dispatchable: DispatchActivity) -> None:
    """
    Process an OfferCaseOwnershipTransfer (Offer(object=Case, target=Actor)) activity.

    This arrives in the *proposed new owner's* inbox. The handler persists
    the offer so the target can later accept or reject it.
    Idempotent: if the offer is already stored, skips.

    Args:
        dispatchable: DispatchActivity containing the OfferCaseOwnershipTransfer
    """
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload.raw_activity

    try:
        dl = get_datalayer()
        existing = dl.get(activity.as_type.value, activity.as_id)
        if existing is not None:
            logger.info(
                "OfferCaseOwnershipTransfer '%s' already stored — skipping (idempotent)",
                activity.as_id,
            )
            return None

        dl.create(activity)
        logger.info(
            "Stored ownership transfer offer '%s' (actor=%s, target=%s)",
            activity.as_id,
            activity.actor,
            activity.target,
        )

    except Exception as e:
        logger.error(
            "Error in offer_case_ownership_transfer for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER)
def accept_case_ownership_transfer(dispatchable: DispatchActivity) -> None:
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
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload.raw_activity

    try:
        dl = get_datalayer()
        offer = rehydrate(obj=activity.as_object)
        case = rehydrate(obj=offer.as_object)

        new_owner_id = (
            activity.actor.as_id
            if hasattr(activity.actor, "as_id")
            else str(activity.actor)
        )
        case_id = case.as_id

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
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER)
def reject_case_ownership_transfer(dispatchable: DispatchActivity) -> None:
    """
    Process a RejectCaseOwnershipTransfer (Reject(object=OfferCaseOwnershipTransfer)) activity.

    This arrives in the *current owner's* inbox after the proposed new owner
    rejects. Case ownership is unchanged. No state change required.

    Args:
        dispatchable: DispatchActivity containing the RejectCaseOwnershipTransfer
    """
    activity = dispatchable.payload.raw_activity

    try:
        offer_ref = activity.as_object
        offer_id = (
            offer_ref.as_id if hasattr(offer_ref, "as_id") else str(offer_ref)
        )
        logger.info(
            "Actor '%s' rejected ownership transfer offer '%s' — ownership unchanged",
            activity.actor,
            offer_id,
        )

    except Exception as e:
        logger.error(
            "Error in reject_case_ownership_transfer for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.INVITE_ACTOR_TO_CASE)
def invite_actor_to_case(dispatchable: DispatchActivity) -> None:
    """
    Process an Invite(actor=CaseOwner, object=Actor, target=Case) activity.

    This arrives in the *invited actor's* inbox. The handler persists the
    Invite so that the actor can later accept or reject it.

    Args:
        dispatchable: DispatchActivity containing the RmInviteToCase activity
    """
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload.raw_activity

    try:
        dl = get_datalayer()
        existing = dl.get(activity.as_type.value, activity.as_id)
        if existing is not None:
            logger.info(
                "Invite '%s' already stored — skipping (idempotent)",
                activity.as_id,
            )
            return None

        dl.create(activity)
        logger.info(
            "Stored invite '%s' (actor=%s, target=%s)",
            activity.as_id,
            activity.as_actor,
            activity.target,
        )

    except Exception as e:
        logger.error(
            "Error in invite_actor_to_case for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE)
def accept_invite_actor_to_case(dispatchable: DispatchActivity) -> None:
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
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.as_vocab.objects.case_participant import CaseParticipant

    activity = dispatchable.payload.raw_activity

    try:
        invite = rehydrate(obj=activity.as_object)
        case = rehydrate(obj=invite.target)
        invitee_ref = invite.as_object
        invitee_id = (
            invitee_ref.as_id
            if hasattr(invitee_ref, "as_id")
            else str(invitee_ref)
        )
        case_id = case.as_id

        dl = get_datalayer()

        existing_ids = [
            (p.as_id if hasattr(p, "as_id") else p)
            for p in case.case_participants
        ]
        if invitee_id in existing_ids:
            logger.info(
                "Actor '%s' already participant in case '%s' — skipping (idempotent)",
                invitee_id,
                case_id,
            )
            return None

        participant = CaseParticipant(
            id=f"{case_id}/participants/{invitee_id.split('/')[-1]}",
            attributed_to=invitee_id,
            context=case_id,
        )
        dl.create(participant)

        case.case_participants.append(participant.as_id)
        dl.update(case_id, object_to_record(case))

        logger.info(
            "Added participant '%s' to case '%s' via accepted invite",
            invitee_id,
            case_id,
        )

    except Exception as e:
        logger.error(
            "Error in accept_invite_actor_to_case for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE)
def reject_invite_actor_to_case(dispatchable: DispatchActivity) -> None:
    """
    Process a Reject(object=RmInviteToCase) activity.

    This arrives in the *case owner's* inbox. The handler logs the rejection;
    no state change is required.

    Args:
        dispatchable: DispatchActivity containing the RmRejectInviteToCase
    """
    activity = dispatchable.payload.raw_activity

    try:
        invite_ref = activity.as_object
        invite_id = (
            invite_ref.as_id
            if hasattr(invite_ref, "as_id")
            else str(invite_ref)
        )
        logger.info(
            "Actor '%s' rejected invitation '%s'",
            activity.as_actor,
            invite_id,
        )

    except Exception as e:
        logger.error(
            "Error in reject_invite_actor_to_case for activity %s: %s",
            activity.as_id,
            str(e),
        )
