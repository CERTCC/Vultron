"""
Handler functions for vulnerability report activities.
"""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.types import DispatchActivity

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.CREATE_REPORT)
def create_report(dispatchable: DispatchActivity) -> None:
    """
    Process a CreateReport activity (Create(VulnerabilityReport)).

    Stores the VulnerabilityReport object in the data layer and the Create activity.

    Args:
        dispatchable: DispatchActivity containing the as_Create with VulnerabilityReport object
    """
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.as_vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    activity = dispatchable.payload.raw_activity

    # Extract the created report
    created_obj = activity.as_object
    if not isinstance(created_obj, VulnerabilityReport):
        logger.error(
            "Expected VulnerabilityReport in create_report, got %s",
            type(created_obj).__name__,
        )
        return None

    actor_id = activity.actor
    logger.info(
        "Actor '%s' creates VulnerabilityReport '%s' (ID: %s)",
        actor_id,
        created_obj.name,
        created_obj.as_id,
    )

    # Get data layer
    dl = get_datalayer()

    # Store the report object
    try:
        dl.create(created_obj)
        logger.info(
            "Stored VulnerabilityReport with ID: %s", created_obj.as_id
        )
    except ValueError as e:
        logger.warning(
            "VulnerabilityReport %s already exists: %s", created_obj.as_id, e
        )

    # Store the create activity
    try:
        dl.create(activity)
        logger.info("Stored CreateReport activity with ID: %s", activity.as_id)
    except ValueError as e:
        logger.warning(
            "CreateReport activity %s already exists: %s", activity.as_id, e
        )

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

    activity = dispatchable.payload.raw_activity

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

    Uses behavior tree execution to orchestrate report validation workflow,
    including status updates, case creation, and activity generation.

    Args:
        dispatchable: DispatchActivity containing the as_Accept with Offer object
    """
    from py_trees.common import Status

    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.as_vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )
    from vultron.behaviors.bridge import BTBridge
    from vultron.behaviors.report.validate_tree import (
        create_validate_report_tree,
    )

    activity = dispatchable.payload.raw_activity

    # Rehydrate the accepted offer and report (validation phase)
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
        "Actor '%s' validates VulnerabilityReport '%s' via BT execution",
        actor_id,
        accepted_report.as_id,
    )

    # Delegate to behavior tree for workflow orchestration
    report_id = accepted_report.as_id
    offer_id = accepted_offer.as_id

    dl = get_datalayer()
    bridge = BTBridge(datalayer=dl)

    # Create and execute validation tree
    tree = create_validate_report_tree(report_id=report_id, offer_id=offer_id)

    # Log tree structure for visibility (DEBUG level logs structure, can be enabled if needed)
    tree_viz = BTBridge.get_tree_visualization(tree, show_status=False)
    logger.debug("Validation BT structure:\n%s", tree_viz)

    result = bridge.execute_with_setup(
        tree, actor_id=actor_id, activity=activity
    )

    # Handle BT execution results with detailed feedback
    if result.status == Status.SUCCESS:
        logger.info(
            "✓ BT execution succeeded for report validation: %s (feedback: %s)",
            report_id,
            result.feedback_message or "none",
        )
    elif result.status == Status.FAILURE:
        logger.error(
            "✗ BT execution failed for report validation: %s - %s",
            report_id,
            result.feedback_message,
        )
        if result.errors:
            for error in result.errors:
                logger.error("  - %s", error)
    else:
        logger.warning(
            "⚠ BT execution incomplete for report validation: %s (status=%s)",
            report_id,
            result.status,
        )

    return None


@verify_semantics(MessageSemantics.INVALIDATE_REPORT)
def invalidate_report(dispatchable: DispatchActivity) -> None:
    """
    Process an InvalidateReport activity (TentativeReject(Offer(VulnerabilityReport))).

    Updates the offer status to TENTATIVELY_REJECTED and report status to INVALID.

    Args:
        dispatchable: DispatchActivity containing the as_TentativeReject with Offer object
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.data.status import (
        OfferStatus,
        ReportStatus,
        set_status,
    )
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.bt.report_management.states import RM
    from vultron.enums import OfferStatusEnum

    activity = dispatchable.payload.raw_activity

    try:
        # Rehydrate actor, offer, and report
        actor = rehydrate(obj=activity.actor)
        actor_id = actor.as_id

        # Rehydrate the rejected offer (may be embedded or reference)
        rejected_offer = rehydrate(activity.as_object)

        # Rehydrate the report that's the subject of the offer
        subject_of_offer = rehydrate(rejected_offer.as_object)

        logger.info(
            "Actor '%s' tentatively rejects offer '%s' of VulnerabilityReport '%s'",
            actor_id,
            rejected_offer.as_id,
            subject_of_offer.as_id,
        )

        # Update offer status
        offer_status = OfferStatus(
            object_type=rejected_offer.as_type,
            object_id=rejected_offer.as_id,
            status=OfferStatusEnum.TENTATIVELY_REJECTED,
            actor_id=actor_id,
        )
        set_status(offer_status)
        logger.info(
            "Set offer '%s' status to TENTATIVELY_REJECTED",
            rejected_offer.as_id,
        )

        # Update report status
        report_status = ReportStatus(
            object_type=subject_of_offer.as_type,
            object_id=subject_of_offer.as_id,
            status=RM.INVALID,
            actor_id=actor_id,
        )
        set_status(report_status)
        logger.info(
            "Set report '%s' status to INVALID", subject_of_offer.as_id
        )

        # Store the activity
        dl = get_datalayer()
        try:
            dl.create(activity)
            logger.info(
                "Stored InvalidateReport activity with ID: %s", activity.as_id
            )
        except ValueError as e:
            logger.warning(
                "InvalidateReport activity %s already exists: %s",
                activity.as_id,
                e,
            )

    except Exception as e:
        logger.error(
            "Error invalidating report in activity %s: %s",
            activity.as_id,
            str(e),
        )

    return None


@verify_semantics(MessageSemantics.ACK_REPORT)
def ack_report(dispatchable: DispatchActivity) -> None:
    """
    Process an AckReport activity (Read(Offer(VulnerabilityReport))).

    Acknowledges receipt of a vulnerability report submission.
    Stores the activity and logs the acknowledgement.

    Args:
        dispatchable: DispatchActivity containing the as_Read with Offer object
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload.raw_activity

    try:
        # Rehydrate actor and offer
        actor = rehydrate(obj=activity.actor)
        actor_id = actor.as_id

        # Rehydrate the offer being acknowledged
        offer = rehydrate(activity.as_object)

        # Rehydrate the report that's the subject of the offer
        subject_of_offer = rehydrate(offer.as_object)

        logger.info(
            "Actor '%s' acknowledges receipt of offer '%s' of VulnerabilityReport '%s'",
            actor_id,
            offer.as_id,
            subject_of_offer.as_id,
        )

        # Store the activity
        dl = get_datalayer()
        try:
            dl.create(activity)
            logger.info(
                "Stored AckReport activity with ID: %s", activity.as_id
            )
        except ValueError as e:
            logger.warning(
                "AckReport activity %s already exists: %s", activity.as_id, e
            )

    except Exception as e:
        logger.error(
            "Error acknowledging report in activity %s: %s",
            activity.as_id,
            str(e),
        )

    return None


@verify_semantics(MessageSemantics.CLOSE_REPORT)
def close_report(dispatchable: DispatchActivity) -> None:
    """
    Process a CloseReport activity (Reject(Offer(VulnerabilityReport))).

    Updates the offer status to REJECTED and report status to CLOSED.

    Args:
        dispatchable: DispatchActivity containing the as_Reject with Offer object
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.data.status import (
        OfferStatus,
        ReportStatus,
        set_status,
    )
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.bt.report_management.states import RM
    from vultron.enums import OfferStatusEnum

    activity = dispatchable.payload.raw_activity

    try:
        # Rehydrate actor, offer, and report
        actor = rehydrate(obj=activity.actor)
        actor_id = actor.as_id

        # Rehydrate the rejected offer (may be embedded or reference)
        rejected_offer = rehydrate(activity.as_object)

        # Rehydrate the report that's the subject of the offer
        subject_of_offer = rehydrate(rejected_offer.as_object)

        logger.info(
            "Actor '%s' rejects offer '%s' of VulnerabilityReport '%s'",
            actor_id,
            rejected_offer.as_id,
            subject_of_offer.as_id,
        )

        # Update offer status
        offer_status = OfferStatus(
            object_type=rejected_offer.as_type,
            object_id=rejected_offer.as_id,
            status=OfferStatusEnum.REJECTED,
            actor_id=actor_id,
        )
        set_status(offer_status)
        logger.info("Set offer '%s' status to REJECTED", rejected_offer.as_id)

        # Update report status
        report_status = ReportStatus(
            object_type=subject_of_offer.as_type,
            object_id=subject_of_offer.as_id,
            status=RM.CLOSED,
            actor_id=actor_id,
        )
        set_status(report_status)
        logger.info("Set report '%s' status to CLOSED", subject_of_offer.as_id)

        # Store the activity
        dl = get_datalayer()
        try:
            dl.create(activity)
            logger.info(
                "Stored CloseReport activity with ID: %s", activity.as_id
            )
        except ValueError as e:
            logger.warning(
                "CloseReport activity %s already exists: %s",
                activity.as_id,
                e,
            )

    except Exception as e:
        logger.error(
            "Error closing report in activity %s: %s",
            activity.as_id,
            str(e),
        )

    return None
