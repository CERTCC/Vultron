"""
Handler functions for vulnerability report activities.
"""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.types import DispatchActivity

from vultron.api.v2.datalayer.abc import DataLayer

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.CREATE_REPORT)
def create_report(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    """
    Process a CreateReport activity (Create(VulnerabilityReport)).

    Stores the VulnerabilityReport object in the data layer and the Create activity.

    Args:
        dispatchable: DispatchActivity containing the as_Create with VulnerabilityReport object
    """
    payload = dispatchable.payload

    # Extract the created report
    created_obj = dispatchable.wire_object

    logger.info(
        "Actor '%s' creates VulnerabilityReport '%s' (ID: %s)",
        payload.actor_id,
        created_obj.name,
        payload.object_id,
    )

    # Store the report object
    try:
        dl.create(dispatchable.wire_object)
        logger.info(
            "Stored VulnerabilityReport with ID: %s", payload.object_id
        )
    except ValueError as e:
        logger.warning(
            "VulnerabilityReport %s already exists: %s", payload.object_id, e
        )

    # Store the create activity
    try:
        dl.create(dispatchable.wire_activity)
        logger.info(
            "Stored CreateReport activity with ID: %s", payload.activity_id
        )
    except ValueError as e:
        logger.warning(
            "CreateReport activity %s already exists: %s",
            payload.activity_id,
            e,
        )

    return None


@verify_semantics(MessageSemantics.SUBMIT_REPORT)
def submit_report(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    """
    Process a SubmitReport activity (Offer(VulnerabilityReport)).

    Stores both the VulnerabilityReport object and the Offer activity in the data layer.

    Args:
        dispatchable: DispatchActivity containing the as_Offer with VulnerabilityReport object
    """
    payload = dispatchable.payload

    # Extract the offered report
    offered_obj = dispatchable.wire_object

    logger.info(
        "Actor '%s' submits VulnerabilityReport '%s' (ID: %s)",
        payload.actor_id,
        offered_obj.name,
        payload.object_id,
    )

    # Store the report object
    try:
        dl.create(dispatchable.wire_object)
        logger.info(
            "Stored VulnerabilityReport with ID: %s", payload.object_id
        )
    except ValueError as e:
        logger.warning(
            "VulnerabilityReport %s already exists: %s", payload.object_id, e
        )

    # Store the offer activity
    try:
        dl.create(dispatchable.wire_activity)
        logger.info(
            "Stored SubmitReport activity with ID: %s", payload.activity_id
        )
    except ValueError as e:
        logger.warning(
            "SubmitReport activity %s already exists: %s",
            payload.activity_id,
            e,
        )

    return None


@verify_semantics(MessageSemantics.VALIDATE_REPORT)
def validate_report(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    """
    Process a ValidateReport activity (Accept(Offer(VulnerabilityReport))).

    Uses behavior tree execution to orchestrate report validation workflow,
    including status updates, case creation, and activity generation.

    Args:
        dispatchable: DispatchActivity containing the as_Accept with Offer object
    """
    from py_trees.common import Status

    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.report.validate_tree import (
        create_validate_report_tree,
    )

    payload = dispatchable.payload

    actor_id = payload.actor_id

    logger.info(
        "Actor '%s' validates VulnerabilityReport '%s' via BT execution",
        actor_id,
        payload.inner_object_id,
    )

    # Delegate to behavior tree for workflow orchestration
    report_id = payload.inner_object_id
    offer_id = payload.object_id

    bridge = BTBridge(datalayer=dl)

    # Create and execute validation tree
    tree = create_validate_report_tree(report_id=report_id, offer_id=offer_id)

    # Log tree structure for visibility (DEBUG level logs structure, can be enabled if needed)
    tree_viz = BTBridge.get_tree_visualization(tree, show_status=False)
    logger.debug("Validation BT structure:\n%s", tree_viz)

    result = bridge.execute_with_setup(
        tree, actor_id=actor_id, activity=dispatchable.wire_activity
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
def invalidate_report(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    """
    Process an InvalidateReport activity (TentativeReject(Offer(VulnerabilityReport))).

    Updates the offer status to TENTATIVELY_REJECTED and report status to INVALID.

    Args:
        dispatchable: DispatchActivity containing the as_TentativeReject with Offer object
    """
    from vultron.api.v2.data.status import (
        OfferStatus,
        ReportStatus,
        set_status,
    )
    from vultron.bt.report_management.states import RM
    from vultron.enums import OfferStatusEnum

    payload = dispatchable.payload

    try:
        actor_id = payload.actor_id

        logger.info(
            "Actor '%s' tentatively rejects offer '%s' of VulnerabilityReport '%s'",
            actor_id,
            payload.object_id,
            payload.inner_object_id,
        )

        # Update offer status
        offer_status = OfferStatus(
            object_type=payload.object_type,
            object_id=payload.object_id,
            status=OfferStatusEnum.TENTATIVELY_REJECTED,
            actor_id=actor_id,
        )
        set_status(offer_status)
        logger.info(
            "Set offer '%s' status to TENTATIVELY_REJECTED",
            payload.object_id,
        )

        # Update report status
        report_status = ReportStatus(
            object_type=payload.inner_object_type,
            object_id=payload.inner_object_id,
            status=RM.INVALID,
            actor_id=actor_id,
        )
        set_status(report_status)
        logger.info(
            "Set report '%s' status to INVALID", payload.inner_object_id
        )

        # Store the activity
        try:
            dl.create(dispatchable.wire_activity)
            logger.info(
                "Stored InvalidateReport activity with ID: %s",
                payload.activity_id,
            )
        except ValueError as e:
            logger.warning(
                "InvalidateReport activity %s already exists: %s",
                payload.activity_id,
                e,
            )

    except Exception as e:
        logger.error(
            "Error invalidating report in activity %s: %s",
            payload.activity_id,
            str(e),
        )

    return None


@verify_semantics(MessageSemantics.ACK_REPORT)
def ack_report(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    """
    Process an AckReport activity (Read(Offer(VulnerabilityReport))).

    Acknowledges receipt of a vulnerability report submission.
    Stores the activity and logs the acknowledgement.

    Args:
        dispatchable: DispatchActivity containing the as_Read with Offer object
    """
    payload = dispatchable.payload

    try:
        logger.info(
            "Actor '%s' acknowledges receipt of offer '%s' of VulnerabilityReport '%s'",
            payload.actor_id,
            payload.object_id,
            payload.inner_object_id,
        )

        # Store the activity
        try:
            dl.create(dispatchable.wire_activity)
            logger.info(
                "Stored AckReport activity with ID: %s", payload.activity_id
            )
        except ValueError as e:
            logger.warning(
                "AckReport activity %s already exists: %s",
                payload.activity_id,
                e,
            )

    except Exception as e:
        logger.error(
            "Error acknowledging report in activity %s: %s",
            payload.activity_id,
            str(e),
        )

    return None


@verify_semantics(MessageSemantics.CLOSE_REPORT)
def close_report(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    """
    Process a CloseReport activity (Reject(Offer(VulnerabilityReport))).

    Updates the offer status to REJECTED and report status to CLOSED.

    Args:
        dispatchable: DispatchActivity containing the as_Reject with Offer object
    """
    from vultron.api.v2.data.status import (
        OfferStatus,
        ReportStatus,
        set_status,
    )
    from vultron.bt.report_management.states import RM
    from vultron.enums import OfferStatusEnum

    payload = dispatchable.payload

    try:
        actor_id = payload.actor_id

        logger.info(
            "Actor '%s' rejects offer '%s' of VulnerabilityReport '%s'",
            actor_id,
            payload.object_id,
            payload.inner_object_id,
        )

        # Update offer status
        offer_status = OfferStatus(
            object_type=payload.object_type,
            object_id=payload.object_id,
            status=OfferStatusEnum.REJECTED,
            actor_id=actor_id,
        )
        set_status(offer_status)
        logger.info("Set offer '%s' status to REJECTED", payload.object_id)

        # Update report status
        report_status = ReportStatus(
            object_type=payload.inner_object_type,
            object_id=payload.inner_object_id,
            status=RM.CLOSED,
            actor_id=actor_id,
        )
        set_status(report_status)
        logger.info(
            "Set report '%s' status to CLOSED", payload.inner_object_id
        )

        # Store the activity
        try:
            dl.create(dispatchable.wire_activity)
            logger.info(
                "Stored CloseReport activity with ID: %s", payload.activity_id
            )
        except ValueError as e:
            logger.warning(
                "CloseReport activity %s already exists: %s",
                payload.activity_id,
                e,
            )

    except Exception as e:
        logger.error(
            "Error closing report in activity %s: %s",
            payload.activity_id,
            str(e),
        )

    return None
