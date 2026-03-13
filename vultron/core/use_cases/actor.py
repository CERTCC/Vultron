"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import cast

from vultron.core.models.events.actor import (
    AcceptCaseOwnershipTransferReceivedEvent,
    AcceptInviteActorToCaseReceivedEvent,
    AcceptSuggestActorToCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
    RejectSuggestActorToCaseReceivedEvent,
    SuggestActorToCaseReceivedEvent,
)
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases._types import CaseModel

logger = logging.getLogger(__name__)


def suggest_actor_to_case(
    event: SuggestActorToCaseReceivedEvent, dl: DataLayer, wire_activity=None
) -> None:
    try:
        existing = dl.get(event.activity_type, event.activity_id)
        if existing is not None:
            logger.info(
                "RecommendActor '%s' already stored — skipping (idempotent)",
                event.activity_id,
            )
            return

        obj_to_store = (
            wire_activity if wire_activity is not None else event.activity
        )
        if obj_to_store is not None:
            dl.create(obj_to_store)
            logger.info(
                "Stored actor recommendation '%s' (actor=%s, object=%s, target=%s)",
                event.activity_id,
                event.actor_id,
                event.object_id,
                event.target_id,
            )
    except Exception as e:
        logger.error(
            "Error in suggest_actor_to_case for activity %s: %s",
            event.activity_id,
            str(e),
        )


def accept_suggest_actor_to_case(
    event: AcceptSuggestActorToCaseReceivedEvent,
    dl: DataLayer,
    wire_activity=None,
) -> None:
    try:
        existing = dl.get(event.activity_type, event.activity_id)
        if existing is not None:
            logger.info(
                "AcceptActorRecommendation '%s' already stored — skipping (idempotent)",
                event.activity_id,
            )
            return

        obj_to_store = (
            wire_activity if wire_activity is not None else event.activity
        )
        if obj_to_store is not None:
            dl.create(obj_to_store)
            logger.info(
                "Stored acceptance of actor recommendation '%s' (actor=%s, object=%s, target=%s)",
                event.activity_id,
                event.actor_id,
                event.object_id,
                event.target_id,
            )
    except Exception as e:
        logger.error(
            "Error in accept_suggest_actor_to_case for activity %s: %s",
            event.activity_id,
            str(e),
        )


def reject_suggest_actor_to_case(
    event: RejectSuggestActorToCaseReceivedEvent, dl: DataLayer
) -> None:
    try:
        logger.info(
            "Actor '%s' rejected recommendation to add actor '%s' to case",
            event.actor_id,
            event.object_id,
        )
    except Exception as e:
        logger.error(
            "Error in reject_suggest_actor_to_case for activity %s: %s",
            event.activity_id,
            str(e),
        )


def offer_case_ownership_transfer(
    event: OfferCaseOwnershipTransferReceivedEvent,
    dl: DataLayer,
    wire_activity=None,
) -> None:
    try:
        existing = dl.get(event.activity_type, event.activity_id)
        if existing is not None:
            logger.info(
                "OfferCaseOwnershipTransferActivity '%s' already stored — skipping (idempotent)",
                event.activity_id,
            )
            return

        obj_to_store = (
            wire_activity if wire_activity is not None else event.activity
        )
        if obj_to_store is not None:
            dl.create(obj_to_store)
            logger.info(
                "Stored ownership transfer offer '%s' (actor=%s, target=%s)",
                event.activity_id,
                event.actor_id,
                event.target_id,
            )
    except Exception as e:
        logger.error(
            "Error in offer_case_ownership_transfer for activity %s: %s",
            event.activity_id,
            str(e),
        )


def accept_case_ownership_transfer(
    event: AcceptCaseOwnershipTransferReceivedEvent, dl: DataLayer
) -> None:
    try:
        case_id = event.inner_object_id
        new_owner_id = event.actor_id
        case = cast(CaseModel, dl.read(case_id))

        if case is None:
            logger.warning(
                "accept_case_ownership_transfer: case '%s' not found", case_id
            )
            return

        current_owner_id = (
            case.attributed_to.as_id
            if hasattr(case.attributed_to, "as_id")
            else (str(case.attributed_to) if case.attributed_to else None)
        )
        if current_owner_id == new_owner_id:
            logger.info(
                "Case '%s' already owned by '%s' — skipping (idempotent)",
                case_id,
                new_owner_id,
            )
            return

        case.attributed_to = new_owner_id  # type: ignore[assignment]
        dl.save(case)
        logger.info(
            "Transferred ownership of case '%s' from '%s' to '%s'",
            case_id,
            current_owner_id,
            new_owner_id,
        )

    except Exception as e:
        logger.error(
            "Error in accept_case_ownership_transfer for activity %s: %s",
            event.activity_id,
            str(e),
        )


def reject_case_ownership_transfer(
    event: RejectCaseOwnershipTransferReceivedEvent, dl: DataLayer
) -> None:
    try:
        logger.info(
            "Actor '%s' rejected ownership transfer offer '%s' — ownership unchanged",
            event.actor_id,
            event.object_id,
        )
    except Exception as e:
        logger.error(
            "Error in reject_case_ownership_transfer for activity %s: %s",
            event.activity_id,
            str(e),
        )


def invite_actor_to_case(
    event: InviteActorToCaseReceivedEvent, dl: DataLayer, wire_activity=None
) -> None:
    try:
        existing = dl.get(event.activity_type, event.activity_id)
        if existing is not None:
            logger.info(
                "Invite '%s' already stored — skipping (idempotent)",
                event.activity_id,
            )
            return

        obj_to_store = (
            wire_activity if wire_activity is not None else event.activity
        )
        if obj_to_store is not None:
            dl.create(obj_to_store)
            logger.info(
                "Stored invite '%s' (actor=%s, target=%s)",
                event.activity_id,
                event.actor_id,
                event.target_id,
            )
    except Exception as e:
        logger.error(
            "Error in invite_actor_to_case for activity %s: %s",
            event.activity_id,
            str(e),
        )


def accept_invite_actor_to_case(
    event: AcceptInviteActorToCaseReceivedEvent, dl: DataLayer
) -> None:
    try:
        case_id = event.inner_target_id
        invitee_id = event.inner_object_id
        case = cast(CaseModel, dl.read(case_id))

        if case is None:
            logger.warning(
                "accept_invite_actor_to_case: case '%s' not found", case_id
            )
            return

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
            return

        active_embargo_id = (
            case.active_embargo.as_id
            if hasattr(case.active_embargo, "as_id")
            else (
                str(case.active_embargo)
                if case.active_embargo is not None
                else None
            )
        )

        participant = VultronParticipant(
            as_id=f"{case_id}/participants/{invitee_id.split('/')[-1]}",
            attributed_to=invitee_id,
            context=case_id,
        )
        if active_embargo_id:
            participant.accepted_embargo_ids.append(active_embargo_id)
        dl.create(participant)

        # Use string IDs to avoid wire-type serialization incompatibility
        case.case_participants.append(participant.as_id)
        case.actor_participant_index[invitee_id] = participant.as_id
        case.record_event(invitee_id, "participant_joined")
        if active_embargo_id:
            case.record_event(active_embargo_id, "embargo_accepted")
        dl.save(case)

        logger.info(
            "Added participant '%s' to case '%s' via accepted invite",
            invitee_id,
            case_id,
        )

    except Exception as e:
        logger.error(
            "Error in accept_invite_actor_to_case for activity %s: %s",
            event.activity_id,
            str(e),
        )


def reject_invite_actor_to_case(
    event: RejectInviteActorToCaseReceivedEvent, dl: DataLayer
) -> None:
    try:
        logger.info(
            "Actor '%s' rejected invitation '%s'",
            event.actor_id,
            event.object_id,
        )
    except Exception as e:
        logger.error(
            "Error in reject_invite_actor_to_case for activity %s: %s",
            event.activity_id,
            str(e),
        )
