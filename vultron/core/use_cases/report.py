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


class CreateReportReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: CreateReportReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CreateReportReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        obj_to_store = request.report
        if obj_to_store is not None:
            try:
                self._dl.create(obj_to_store)
                logger.info(
                    "Stored VulnerabilityReport with ID: %s", request.object_id
                )
            except ValueError as e:
                logger.warning(
                    "VulnerabilityReport %s already exists: %s",
                    request.object_id,
                    e,
                )

        if request.activity is not None:
            try:
                self._dl.create(request.activity)
                logger.info(
                    "Stored CreateReport activity with ID: %s",
                    request.activity_id,
                )
            except ValueError as e:
                logger.warning(
                    "CreateReport activity %s already exists: %s",
                    request.activity_id,
                    e,
                )


class SubmitReportReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: SubmitReportReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: SubmitReportReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        obj_to_store = request.report
        if obj_to_store is not None:
            try:
                self._dl.create(obj_to_store)
                logger.info(
                    "Stored VulnerabilityReport with ID: %s", request.object_id
                )
            except ValueError as e:
                logger.warning(
                    "VulnerabilityReport %s already exists: %s",
                    request.object_id,
                    e,
                )

        if request.activity is not None:
            try:
                self._dl.create(request.activity)
                logger.info(
                    "Stored SubmitReport activity with ID: %s",
                    request.activity_id,
                )
            except ValueError as e:
                logger.warning(
                    "SubmitReport activity %s already exists: %s",
                    request.activity_id,
                    e,
                )


class ValidateReportReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: ValidateReportReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: ValidateReportReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        from py_trees.common import Status
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.report.validate_tree import (
            create_validate_report_tree,
        )

        actor_id = request.actor_id
        report_id = request.inner_object_id
        offer_id = request.object_id

        logger.info(
            "Actor '%s' validates VulnerabilityReport '%s' via BT execution",
            actor_id,
            report_id,
        )

        bridge = BTBridge(datalayer=self._dl)
        tree = create_validate_report_tree(
            report_id=report_id, offer_id=offer_id
        )
        result = bridge.execute_with_setup(
            tree, actor_id=actor_id, activity=request
        )

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


class InvalidateReportReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: InvalidateReportReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: InvalidateReportReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        actor_id = request.actor_id
        logger.info(
            "Actor '%s' tentatively rejects offer '%s' of VulnerabilityReport '%s'",
            actor_id,
            request.object_id,
            request.inner_object_id,
        )
        set_status(
            OfferStatus(
                object_type=request.object_type or "Offer",
                object_id=request.object_id,
                status=OfferStatusEnum.TENTATIVELY_REJECTED,
                actor_id=actor_id,
            )
        )
        set_status(
            ReportStatus(
                object_type=request.inner_object_type or "VulnerabilityReport",
                object_id=request.inner_object_id,
                status=RM.INVALID,
                actor_id=actor_id,
            )
        )
        if request.activity is not None:
            try:
                self._dl.create(request.activity)
                logger.info(
                    "Stored InvalidateReport activity with ID: %s",
                    request.activity_id,
                )
            except ValueError as e:
                logger.warning(
                    "InvalidateReport activity %s already exists: %s",
                    request.activity_id,
                    e,
                )


class AckReportReceivedUseCase:
    def __init__(self, dl: DataLayer, request: AckReportReceivedEvent) -> None:
        self._dl = dl
        self._request: AckReportReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.info(
            "Actor '%s' acknowledges receipt of offer '%s' of VulnerabilityReport '%s'",
            request.actor_id,
            request.object_id,
            request.inner_object_id,
        )
        if request.activity is not None:
            try:
                self._dl.create(request.activity)
                logger.info(
                    "Stored AckReport activity with ID: %s",
                    request.activity_id,
                )
            except ValueError as e:
                logger.warning(
                    "AckReport activity %s already exists: %s",
                    request.activity_id,
                    e,
                )


class CloseReportReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: CloseReportReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CloseReportReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        actor_id = request.actor_id
        logger.info(
            "Actor '%s' rejects offer '%s' of VulnerabilityReport '%s'",
            actor_id,
            request.object_id,
            request.inner_object_id,
        )
        set_status(
            OfferStatus(
                object_type=request.object_type or "Offer",
                object_id=request.object_id,
                status=OfferStatusEnum.REJECTED,
                actor_id=actor_id,
            )
        )
        set_status(
            ReportStatus(
                object_type=request.inner_object_type or "VulnerabilityReport",
                object_id=request.inner_object_id,
                status=RM.CLOSED,
                actor_id=actor_id,
            )
        )
        if request.activity is not None:
            try:
                self._dl.create(request.activity)
                logger.info(
                    "Stored CloseReport activity with ID: %s",
                    request.activity_id,
                )
            except ValueError as e:
                logger.warning(
                    "CloseReport activity %s already exists: %s",
                    request.activity_id,
                    e,
                )
