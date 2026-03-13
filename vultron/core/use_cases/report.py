"""Use cases for vulnerability report activities."""

import logging

from vultron.core.models.events.report import (
    AckReportReceivedEvent,
    CloseReportReceivedEvent,
    CreateReportReceivedEvent,
    InvalidateReportReceivedEvent,
    SubmitReportReceivedEvent,
    ValidateReportReceivedEvent,
)
from vultron.core.models.status import (
    OfferStatus,
    OfferStatusEnum,
    ReportStatus,
    set_status,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.bt.report_management.states import RM

logger = logging.getLogger(__name__)


def create_report(event: CreateReportReceivedEvent, dl: DataLayer) -> None:
    obj_to_store = event.report
    if obj_to_store is not None:
        try:
            dl.create(obj_to_store)
            logger.info(
                "Stored VulnerabilityReport with ID: %s", event.object_id
            )
        except ValueError as e:
            logger.warning(
                "VulnerabilityReport %s already exists: %s", event.object_id, e
            )

    if event.activity is not None:
        try:
            dl.create(event.activity)
            logger.info(
                "Stored CreateReport activity with ID: %s", event.activity_id
            )
        except ValueError as e:
            logger.warning(
                "CreateReport activity %s already exists: %s",
                event.activity_id,
                e,
            )


def submit_report(event: SubmitReportReceivedEvent, dl: DataLayer) -> None:
    obj_to_store = event.report
    if obj_to_store is not None:
        try:
            dl.create(obj_to_store)
            logger.info(
                "Stored VulnerabilityReport with ID: %s", event.object_id
            )
        except ValueError as e:
            logger.warning(
                "VulnerabilityReport %s already exists: %s", event.object_id, e
            )

    if event.activity is not None:
        try:
            dl.create(event.activity)
            logger.info(
                "Stored SubmitReport activity with ID: %s", event.activity_id
            )
        except ValueError as e:
            logger.warning(
                "SubmitReport activity %s already exists: %s",
                event.activity_id,
                e,
            )


def validate_report(event: ValidateReportReceivedEvent, dl: DataLayer) -> None:
    from py_trees.common import Status
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.report.validate_tree import (
        create_validate_report_tree,
    )

    actor_id = event.actor_id
    report_id = event.inner_object_id
    offer_id = event.object_id

    logger.info(
        "Actor '%s' validates VulnerabilityReport '%s' via BT execution",
        actor_id,
        report_id,
    )

    bridge = BTBridge(datalayer=dl)
    tree = create_validate_report_tree(report_id=report_id, offer_id=offer_id)
    result = bridge.execute_with_setup(tree, actor_id=actor_id, activity=event)

    if result.status == Status.SUCCESS:
        logger.info("✓ BT validation succeeded for report: %s", report_id)
    elif result.status == Status.FAILURE:
        logger.error(
            "✗ BT validation failed for report: %s — %s",
            report_id,
            result.feedback_message,
        )
        for err in result.errors or []:
            logger.error("  - %s", err)
    else:
        logger.warning(
            "⚠ BT validation incomplete for report: %s (status=%s)",
            report_id,
            result.status,
        )


def invalidate_report(
    event: InvalidateReportReceivedEvent, dl: DataLayer
) -> None:
    try:
        actor_id = event.actor_id
        logger.info(
            "Actor '%s' tentatively rejects offer '%s' of VulnerabilityReport '%s'",
            actor_id,
            event.object_id,
            event.inner_object_id,
        )
        set_status(
            OfferStatus(
                object_type=event.object_type or "Offer",
                object_id=event.object_id,
                status=OfferStatusEnum.TENTATIVELY_REJECTED,
                actor_id=actor_id,
            )
        )
        set_status(
            ReportStatus(
                object_type=event.inner_object_type or "VulnerabilityReport",
                object_id=event.inner_object_id,
                status=RM.INVALID,
                actor_id=actor_id,
            )
        )
        if event.activity is not None:
            try:
                dl.create(event.activity)
                logger.info(
                    "Stored InvalidateReport activity with ID: %s",
                    event.activity_id,
                )
            except ValueError as e:
                logger.warning(
                    "InvalidateReport activity %s already exists: %s",
                    event.activity_id,
                    e,
                )
    except Exception as e:
        logger.error(
            "Error invalidating report in activity %s: %s",
            event.activity_id,
            str(e),
        )


def ack_report(event: AckReportReceivedEvent, dl: DataLayer) -> None:
    try:
        logger.info(
            "Actor '%s' acknowledges receipt of offer '%s' of VulnerabilityReport '%s'",
            event.actor_id,
            event.object_id,
            event.inner_object_id,
        )
        if event.activity is not None:
            try:
                dl.create(event.activity)
                logger.info(
                    "Stored AckReport activity with ID: %s", event.activity_id
                )
            except ValueError as e:
                logger.warning(
                    "AckReport activity %s already exists: %s",
                    event.activity_id,
                    e,
                )
    except Exception as e:
        logger.error(
            "Error acknowledging report in activity %s: %s",
            event.activity_id,
            str(e),
        )


def close_report(event: CloseReportReceivedEvent, dl: DataLayer) -> None:
    try:
        actor_id = event.actor_id
        logger.info(
            "Actor '%s' rejects offer '%s' of VulnerabilityReport '%s'",
            actor_id,
            event.object_id,
            event.inner_object_id,
        )
        set_status(
            OfferStatus(
                object_type=event.object_type or "Offer",
                object_id=event.object_id,
                status=OfferStatusEnum.REJECTED,
                actor_id=actor_id,
            )
        )
        set_status(
            ReportStatus(
                object_type=event.inner_object_type or "VulnerabilityReport",
                object_id=event.inner_object_id,
                status=RM.CLOSED,
                actor_id=actor_id,
            )
        )
        if event.activity is not None:
            try:
                dl.create(event.activity)
                logger.info(
                    "Stored CloseReport activity with ID: %s",
                    event.activity_id,
                )
            except ValueError as e:
                logger.warning(
                    "CloseReport activity %s already exists: %s",
                    event.activity_id,
                    e,
                )
    except Exception as e:
        logger.error(
            "Error closing report in activity %s: %s",
            event.activity_id,
            str(e),
        )
