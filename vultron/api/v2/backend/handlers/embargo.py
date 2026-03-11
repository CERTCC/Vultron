"""
Handler functions for embargo management activities.
"""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.types import DispatchActivity

from vultron.api.v2.datalayer.abc import DataLayer

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.CREATE_EMBARGO_EVENT)
def create_embargo_event(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process a Create(EmbargoEvent) activity.

    Persists the EmbargoEvent to the DataLayer so it can be referenced by
    subsequent add/activate/announce embargo activities.

    Args:
        dispatchable: DispatchActivity containing the Create(EmbargoEvent)
    """
    payload = dispatchable.payload

    try:
        existing = dl.get(payload.object_type, payload.object_id)
        if existing is not None:
            logger.info(
                "EmbargoEvent '%s' already stored — skipping (idempotent)",
                payload.object_id,
            )
            return None

        dl.create(dispatchable.wire_object)
        logger.info("Stored EmbargoEvent '%s'", payload.object_id)

    except Exception as e:
        logger.error(
            "Error in create_embargo_event for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE)
def add_embargo_event_to_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process an Add(EmbargoEvent, target=VulnerabilityCase) or
    ActivateEmbargo(EmbargoEvent, target=VulnerabilityCase) activity.

    Links the embargo event to the case and sets the case EM state to ACTIVE.
    Idempotent: if the case already has this embargo active, skips.

    Args:
        dispatchable: DispatchActivity containing the Add/ActivateEmbargo
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.db_record import object_to_record

    payload = dispatchable.payload

    try:
        embargo = rehydrate(payload.object_id)
        case = rehydrate(payload.target_id)
        embargo_id = payload.object_id
        case_id = payload.target_id

        current_embargo_id = (
            case.active_embargo.as_id
            if hasattr(case.active_embargo, "as_id")
            else (
                str(case.active_embargo)
                if case.active_embargo is not None
                else None
            )
        )
        if current_embargo_id == embargo_id:
            logger.info(
                "Case '%s' already has embargo '%s' active — skipping (idempotent)",
                case_id,
                embargo_id,
            )
            return None

        case.set_embargo(payload.object_id)
        dl.update(case_id, object_to_record(case))
        logger.info(
            "Activated embargo '%s' on case '%s'",
            embargo_id,
            case_id,
        )

    except Exception as e:
        logger.error(
            "Error in add_embargo_event_to_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE)
def remove_embargo_event_from_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process a Remove(EmbargoEvent, origin=VulnerabilityCase) activity.

    Clears the active embargo from the case and sets EM state accordingly.
    Per ActivityStreams spec, the `origin` field holds the context from which
    the object is removed.

    Args:
        dispatchable: DispatchActivity containing the RemoveEmbargoFromCase
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.db_record import object_to_record
    from vultron.bt.embargo_management.states import EM

    payload = dispatchable.payload

    try:
        case = rehydrate(payload.origin_id)
        embargo_id = payload.object_id
        case_id = payload.origin_id

        current_embargo_id = (
            case.active_embargo.as_id
            if hasattr(case.active_embargo, "as_id")
            else (
                str(case.active_embargo)
                if case.active_embargo is not None
                else None
            )
        )
        if current_embargo_id != embargo_id:
            logger.info(
                "Case '%s' does not have embargo '%s' active — skipping",
                case_id,
                embargo_id,
            )
            return None

        case.active_embargo = None
        case.current_status.em_state = EM.EMBARGO_MANAGEMENT_NONE
        dl.update(case_id, object_to_record(case))
        logger.info(
            "Removed embargo '%s' from case '%s'",
            embargo_id,
            case_id,
        )

    except Exception as e:
        logger.error(
            "Error in remove_embargo_event_from_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE)
def announce_embargo_event_to_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process an Announce(EmbargoEvent, context=VulnerabilityCase) activity.

    Records the announcement in the case activity log. The AnnounceEmbargo
    activity informs case participants of the current embargo status.

    Args:
        dispatchable: DispatchActivity containing the AnnounceEmbargo
    """
    payload = dispatchable.payload

    try:
        case_id = payload.context_id

        logger.info(
            "Received embargo announcement '%s' on case '%s'",
            payload.activity_id,
            case_id,
        )

    except Exception as e:
        logger.error(
            "Error in announce_embargo_event_to_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.INVITE_TO_EMBARGO_ON_CASE)
def invite_to_embargo_on_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process an EmProposeEmbargo (Invite(EmbargoEvent, context=VulnerabilityCase)) activity.

    Persists the proposal so participants can later accept or reject it.
    This arrives in the *invitee's* inbox. Idempotent: if the proposal is
    already stored, skips.

    Args:
        dispatchable: DispatchActivity containing the EmProposeEmbargo
    """
    payload = dispatchable.payload

    try:
        existing = dl.get(payload.activity_type, payload.activity_id)
        if existing is not None:
            logger.info(
                "EmProposeEmbargo '%s' already stored — skipping (idempotent)",
                payload.activity_id,
            )
            return None

        dl.create(dispatchable.wire_activity)
        logger.info(
            "Stored embargo proposal '%s' (actor=%s, context=%s)",
            payload.activity_id,
            payload.actor_id,
            payload.context_id,
        )

    except Exception as e:
        logger.error(
            "Error in invite_to_embargo_on_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE)
def accept_invite_to_embargo_on_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process an EmAcceptEmbargo (Accept(object=EmProposeEmbargo)) activity.

    This arrives in the *proposer's* inbox. The handler rehydrates the
    proposal, retrieves the proposed EmbargoEvent, and activates it on the
    case via set_embargo(). Idempotent: if the case already has this embargo
    active, skips.

    Args:
        dispatchable: DispatchActivity containing the EmAcceptEmbargo
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.db_record import object_to_record

    payload = dispatchable.payload

    try:
        embargo_id = payload.inner_object_id
        case = (
            rehydrate(payload.inner_context_id)
            if payload.inner_context_id
            else rehydrate(dl.read(payload.object_id).context)
        )
        case_id = case.as_id

        current_embargo_id = (
            case.active_embargo.as_id
            if hasattr(case.active_embargo, "as_id")
            else (
                str(case.active_embargo)
                if case.active_embargo is not None
                else None
            )
        )
        if current_embargo_id == embargo_id:
            logger.info(
                "Case '%s' already has embargo '%s' active — skipping (idempotent)",
                case_id,
                embargo_id,
            )
            return None

        case.set_embargo(embargo_id)

        accepting_actor_id = payload.actor_id
        participant_id = case.actor_participant_index.get(accepting_actor_id)
        if participant_id:
            participant = rehydrate(participant_id)
            if embargo_id not in participant.accepted_embargo_ids:
                participant.accepted_embargo_ids.append(embargo_id)
                dl.update(participant_id, object_to_record(participant))
                logger.info(
                    "Recorded embargo acceptance '%s' for participant '%s'",
                    embargo_id,
                    accepting_actor_id,
                )
        else:
            logger.warning(
                "Accepting actor '%s' has no CaseParticipant in case '%s' — "
                "cannot record embargo acceptance",
                accepting_actor_id,
                case_id,
            )

        case.record_event(embargo_id, "embargo_accepted")
        dl.update(case_id, object_to_record(case))
        logger.info(
            "Accepted embargo proposal '%s'; activated embargo '%s' on case '%s'",
            payload.object_id,
            embargo_id,
            case_id,
        )

    except Exception as e:
        logger.error(
            "Error in accept_invite_to_embargo_on_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE)
def reject_invite_to_embargo_on_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process an EmRejectEmbargo (Reject(object=EmProposeEmbargo)) activity.

    This arrives in the *proposer's* inbox. The handler logs the rejection;
    no state change is required.

    Args:
        dispatchable: DispatchActivity containing the EmRejectEmbargo
    """
    payload = dispatchable.payload

    try:
        logger.info(
            "Actor '%s' rejected embargo proposal '%s'",
            payload.actor_id,
            payload.object_id,
        )

    except Exception as e:
        logger.error(
            "Error in reject_invite_to_embargo_on_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )
