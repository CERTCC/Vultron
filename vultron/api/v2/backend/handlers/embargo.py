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
    activity = dispatchable.payload.raw_activity

    try:
        embargo = activity.as_object

        existing = dl.get(embargo.as_type.value, embargo.as_id)
        if existing is not None:
            logger.info(
                "EmbargoEvent '%s' already stored — skipping (idempotent)",
                embargo.as_id,
            )
            return None

        dl.create(embargo)
        logger.info("Stored EmbargoEvent '%s'", embargo.as_id)

    except Exception as e:
        logger.error(
            "Error in create_embargo_event for activity %s: %s",
            activity.as_id,
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

    activity = dispatchable.payload.raw_activity

    try:
        embargo = rehydrate(obj=activity.as_object)
        case = rehydrate(obj=activity.target)

        embargo_id = (
            embargo.as_id if hasattr(embargo, "as_id") else str(embargo)
        )
        case_id = case.as_id if hasattr(case, "as_id") else str(case)

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

        case.set_embargo(
            embargo.as_id if hasattr(embargo, "as_id") else embargo
        )
        dl.update(case_id, object_to_record(case))
        logger.info(
            "Activated embargo '%s' on case '%s'",
            embargo_id,
            case_id,
        )

    except Exception as e:
        logger.error(
            "Error in add_embargo_event_to_case for activity %s: %s",
            activity.as_id,
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

    activity = dispatchable.payload.raw_activity

    try:
        case = rehydrate(obj=activity.origin)
        embargo = activity.as_object

        embargo_id = (
            embargo.as_id if hasattr(embargo, "as_id") else str(embargo)
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
            activity.as_id,
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
    from vultron.api.v2.data.rehydration import rehydrate

    activity = dispatchable.payload.raw_activity

    try:
        case = rehydrate(obj=activity.context)
        case_id = case.as_id

        logger.info(
            "Received embargo announcement '%s' on case '%s'",
            activity.as_id,
            case_id,
        )

    except Exception as e:
        logger.error(
            "Error in announce_embargo_event_to_case for activity %s: %s",
            activity.as_id,
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
    activity = dispatchable.payload.raw_activity

    try:
        existing = dl.get(activity.as_type.value, activity.as_id)
        if existing is not None:
            logger.info(
                "EmProposeEmbargo '%s' already stored — skipping (idempotent)",
                activity.as_id,
            )
            return None

        dl.create(activity)
        logger.info(
            "Stored embargo proposal '%s' (actor=%s, context=%s)",
            activity.as_id,
            activity.as_actor,
            activity.context,
        )

    except Exception as e:
        logger.error(
            "Error in invite_to_embargo_on_case for activity %s: %s",
            activity.as_id,
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

    activity = dispatchable.payload.raw_activity

    try:
        proposal = rehydrate(obj=activity.as_object)
        embargo = rehydrate(obj=proposal.as_object)
        case = rehydrate(obj=proposal.context)

        embargo_id = embargo.as_id
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

        case.set_embargo(
            embargo.as_id if hasattr(embargo, "as_id") else embargo
        )
        dl.update(case_id, object_to_record(case))
        logger.info(
            "Accepted embargo proposal '%s'; activated embargo '%s' on case '%s'",
            proposal.as_id,
            embargo_id,
            case_id,
        )

    except Exception as e:
        logger.error(
            "Error in accept_invite_to_embargo_on_case for activity %s: %s",
            activity.as_id,
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
    activity = dispatchable.payload.raw_activity

    try:
        proposal_ref = activity.as_object
        proposal_id = (
            proposal_ref.as_id
            if hasattr(proposal_ref, "as_id")
            else str(proposal_ref)
        )
        logger.info(
            "Actor '%s' rejected embargo proposal '%s'",
            activity.as_actor,
            proposal_id,
        )

    except Exception as e:
        logger.error(
            "Error in reject_invite_to_embargo_on_case for activity %s: %s",
            activity.as_id,
            str(e),
        )
