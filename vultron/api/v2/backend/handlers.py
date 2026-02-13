"""
Provides handler functions for specific activities in the Vultron API v2 backend.
"""

import logging
from functools import wraps

from vultron.api.v2.errors import (
    VultronApiHandlerMissingSemanticError,
    VultronApiHandlerSemanticMismatchError,
)
from vultron.enums import MessageSemantics
from vultron.semantic_map import find_matching_semantics
from vultron.types import DispatchActivity

logger = logging.getLogger(__name__)


def verify_semantics(expected_semantic_type: MessageSemantics):
    def decorator(func):
        @wraps(func)
        def wrapper(dispatchable: DispatchActivity):
            if not dispatchable.semantic_type:
                logger.error(
                    "Dispatchable activity %s is missing semantic_type",
                    dispatchable,
                )
                raise VultronApiHandlerMissingSemanticError()

            computed = find_matching_semantics(dispatchable.payload)

            if computed != expected_semantic_type:
                logger.error(
                    "Dispatchable activity %s claims semantic_type %s that does not match its payload (%s)",
                    dispatchable,
                    expected_semantic_type,
                    computed,
                )
                raise VultronApiHandlerSemanticMismatchError(
                    expected=expected_semantic_type, actual=computed
                )

            return func(dispatchable)

        return wrapper

    return decorator


@verify_semantics(MessageSemantics.CREATE_REPORT)
def create_report(dispatchable: DispatchActivity) -> None:
    logger.debug("create_report handler called: %s", dispatchable)

    return None


@verify_semantics(MessageSemantics.SUBMIT_REPORT)
def submit_report(dispatchable: DispatchActivity) -> None:
    """
    Process a SubmitReport activity (Offer(VulnerabilityReport)).

    Stores both the VulnerabilityReport object and the Offer activity in the data layer.

    Args:
        dispatchable: DispatchActivity containing the as_Offer with VulnerabilityReport object
    """
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.as_vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    activity = dispatchable.payload

    # Extract the offered report
    offered_obj = activity.as_object
    if not isinstance(offered_obj, VulnerabilityReport):
        logger.error(
            "Expected VulnerabilityReport in submit_report, got %s",
            type(offered_obj).__name__,
        )
        return None

    actor_id = activity.actor
    logger.info(
        "Actor '%s' submits VulnerabilityReport '%s' (ID: %s)",
        actor_id,
        offered_obj.name,
        offered_obj.as_id,
    )

    # Get data layer
    dl = get_datalayer()

    # Store the report object
    try:
        dl.create(offered_obj)
        logger.info(
            "Stored VulnerabilityReport with ID: %s", offered_obj.as_id
        )
    except ValueError as e:
        logger.warning(
            "VulnerabilityReport %s already exists: %s", offered_obj.as_id, e
        )

    # Store the offer activity
    try:
        dl.create(activity)
        logger.info("Stored SubmitReport activity with ID: %s", activity.as_id)
    except ValueError as e:
        logger.warning(
            "SubmitReport activity %s already exists: %s", activity.as_id, e
        )

    return None


@verify_semantics(MessageSemantics.VALIDATE_REPORT)
def validate_report(dispatchable: DispatchActivity) -> None:
    """
    Process a ValidateReport activity (Accept(Offer(VulnerabilityReport))).

    Updates report status to VALID, creates a VulnerabilityCase containing the
    validated report, and generates a CreateCase activity in the actor's outbox.

    Args:
        dispatchable: DispatchActivity containing the as_Accept with Offer object
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.data.status import (
        OfferStatus,
        ReportStatus,
        set_status,
    )
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.as_vocab.activities.case import CreateCase
    from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
    from vultron.as_vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )
    from vultron.bt.report_management.states import RM
    from vultron.enums import OfferStatusEnum

    activity = dispatchable.payload

    # Rehydrate the accepted offer and report
    try:
        accepted_offer = rehydrate(activity.as_object)
        accepted_report = rehydrate(accepted_offer.as_object)
    except (ValueError, KeyError) as e:
        logger.error(
            "Failed to rehydrate offer or report in validate_report: %s", e
        )
        return None

    # Verify we have a VulnerabilityReport
    if not isinstance(accepted_report, VulnerabilityReport):
        logger.error(
            "Expected VulnerabilityReport in validate_report, got %s",
            type(accepted_report).__name__,
        )
        return None

    # Rehydrate actor
    try:
        actor = rehydrate(activity.actor)
        actor_id = actor.as_id
    except (ValueError, KeyError) as e:
        logger.error("Failed to rehydrate actor in validate_report: %s", e)
        return None

    logger.info(
        "Actor '%s' validates VulnerabilityReport '%s'",
        actor_id,
        accepted_report.as_id,
    )

    # Update offer status to ACCEPTED
    offer_status = OfferStatus(
        object_type=accepted_offer.as_type,
        object_id=accepted_offer.as_id,
        status=OfferStatusEnum.ACCEPTED,
        actor_id=actor_id,
    )
    set_status(offer_status)
    logger.info(
        "Set offer status to ACCEPTED for offer %s", accepted_offer.as_id
    )

    # Update report status to VALID
    report_status = ReportStatus(
        object_type=accepted_report.as_type,
        object_id=accepted_report.as_id,
        status=RM.VALID,
        actor_id=actor_id,
    )
    set_status(report_status)
    logger.info(
        "Set report status to VALID for report %s", accepted_report.as_id
    )

    # Create a VulnerabilityCase
    case = VulnerabilityCase(
        name=f"Case for Report {accepted_report.as_id}",
        vulnerability_reports=[accepted_report],
        attributed_to=actor_id,
    )

    # Store the case in data layer
    dl = get_datalayer()
    try:
        dl.create(case)
        logger.info("Created VulnerabilityCase: %s: %s", case.as_id, case.name)
    except ValueError as e:
        logger.warning(
            "VulnerabilityCase %s already exists: %s", case.as_id, e
        )

    # Collect addressees
    addressees = []
    for x in [actor, accepted_report.attributed_to, accepted_offer.to]:
        if x is None:
            continue
        if isinstance(x, str):
            addressees.append(x)
        elif isinstance(x, list):
            for item in x:
                if isinstance(item, str):
                    addressees.append(item)
                elif hasattr(item, "as_id"):
                    addressees.append(item.as_id)
        elif hasattr(x, "as_id"):
            addressees.append(x.as_id)

    # Unique addressees
    addressees = list(set(addressees))
    logger.info("Notifying addressees: %s", addressees)

    # Create a CreateCase activity
    create_case_activity = CreateCase(
        actor=actor_id, object=case.as_id, to=addressees
    )

    # Store the CreateCase activity
    try:
        dl.create(create_case_activity)
        logger.info(
            "Created CreateCase activity: %s", create_case_activity.as_id
        )
    except ValueError as e:
        logger.warning(
            "CreateCase activity %s already exists: %s",
            create_case_activity.as_id,
            e,
        )

    # Add to actor's outbox
    try:
        actor_obj = dl.read(actor_id, raise_on_missing=True)
        if hasattr(actor_obj, "outbox") and hasattr(actor_obj.outbox, "items"):
            actor_obj.outbox.items.append(create_case_activity.as_id)
            logger.info(
                "Added CreateCase activity to actor outbox: %s",
                create_case_activity.as_id,
            )
        else:
            logger.error(
                "Actor %s has no outbox or outbox.items attribute", actor_id
            )
    except Exception as e:
        logger.error(
            "Failed to add CreateCase activity to actor outbox: %s", e
        )

    return None


@verify_semantics(MessageSemantics.INVALIDATE_REPORT)
def invalidate_report(dispatchable: DispatchActivity) -> None:
    logger.debug("invalidate_report handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ACK_REPORT)
def ack_report(dispatchable: DispatchActivity) -> None:
    logger.debug("ack_report handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.CLOSE_REPORT)
def close_report(dispatchable: DispatchActivity) -> None:
    logger.debug("close_report handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.CREATE_CASE)
def create_case(dispatchable: DispatchActivity) -> None:
    logger.debug("create_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_REPORT_TO_CASE)
def add_report_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("add_report_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.SUGGEST_ACTOR_TO_CASE)
def suggest_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("suggest_actor_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE)
def accept_suggest_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "accept_suggest_actor_to_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE)
def reject_suggest_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "reject_suggest_actor_to_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER)
def offer_case_ownership_transfer(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "offer_case_ownership_transfer handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER)
def accept_case_ownership_transfer(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "accept_case_ownership_transfer handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER)
def reject_case_ownership_transfer(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "reject_case_ownership_transfer handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.INVITE_ACTOR_TO_CASE)
def invite_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("invite_actor_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE)
def accept_invite_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "accept_invite_actor_to_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE)
def reject_invite_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "reject_invite_actor_to_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.CREATE_EMBARGO_EVENT)
def create_embargo_event(dispatchable: DispatchActivity) -> None:
    logger.debug("create_embargo_event handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE)
def add_embargo_event_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("add_embargo_event_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE)
def remove_embargo_event_from_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "remove_embargo_event_from_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE)
def announce_embargo_event_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "announce_embargo_event_to_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.INVITE_TO_EMBARGO_ON_CASE)
def invite_to_embargo_on_case(dispatchable: DispatchActivity) -> None:
    logger.debug("invite_to_embargo_on_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE)
def accept_invite_to_embargo_on_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "accept_invite_to_embargo_on_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE)
def reject_invite_to_embargo_on_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "reject_invite_to_embargo_on_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.CLOSE_CASE)
def close_case(dispatchable: DispatchActivity) -> None:
    logger.debug("close_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.CREATE_CASE_PARTICIPANT)
def create_case_participant(dispatchable: DispatchActivity) -> None:
    logger.debug("create_case_participant handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE)
def add_case_participant_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "add_case_participant_to_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE)
def remove_case_participant_from_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "remove_case_participant_from_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.CREATE_NOTE)
def create_note(dispatchable: DispatchActivity) -> None:
    logger.debug("create_note handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_NOTE_TO_CASE)
def add_note_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("add_note_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.REMOVE_NOTE_FROM_CASE)
def remove_note_from_case(dispatchable: DispatchActivity) -> None:
    logger.debug("remove_note_from_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.CREATE_CASE_STATUS)
def create_case_status(dispatchable: DispatchActivity) -> None:
    logger.debug("create_case_status handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_CASE_STATUS_TO_CASE)
def add_case_status_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("add_case_status_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.CREATE_PARTICIPANT_STATUS)
def create_participant_status(dispatchable: DispatchActivity) -> None:
    logger.debug("create_participant_status handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT)
def add_participant_status_to_participant(
    dispatchable: DispatchActivity,
) -> None:
    logger.debug(
        "add_participant_status_to_participant handler called: %s",
        dispatchable,
    )
    return None


@verify_semantics(MessageSemantics.UNKNOWN)
def unknown(dispatchable: DispatchActivity) -> None:
    logger.warning("unknown handler called for dispatchable: %s", dispatchable)
    return None
