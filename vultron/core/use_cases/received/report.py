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
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases.received.case import (
    CloseCaseUseCase,
    InvalidateCaseUseCase,
    ValidateCaseUseCase,
)
from vultron.errors import VultronValidationError

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
                    "Stored VulnerabilityReport with ID: %s", request.report_id
                )
            except ValueError as e:
                # The inbox endpoint pre-stores inline nested objects before
                # dispatching (actors.py), so a duplicate here is expected
                # and not an error condition.
                logger.debug(
                    "VulnerabilityReport %s already exists (pre-stored by "
                    "inbox endpoint): %s",
                    request.report_id,
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
                    "Stored VulnerabilityReport with ID: %s", request.report_id
                )
            except ValueError as e:
                # The inbox endpoint pre-stores inline nested objects before
                # dispatching (actors.py), so a duplicate here is expected
                # and not an error condition.
                logger.debug(
                    "VulnerabilityReport %s already exists (pre-stored by "
                    "inbox endpoint): %s",
                    request.report_id,
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
                # The inbox endpoint pre-stores activities before dispatching,
                # so a duplicate here is expected and not an error condition.
                logger.debug(
                    "SubmitReport activity %s already exists (pre-stored by "
                    "inbox endpoint): %s",
                    request.activity_id,
                    e,
                )

        if request.report_id:
            vendor_actor_id = request.target_id
            if vendor_actor_id is None:
                logger.warning(
                    "SubmitReportReceivedUseCase: vendor actor_id not "
                    "available (Offer.target not set) for report '%s' — "
                    "skipping case creation",
                    request.report_id,
                )
                return

            logger.info(
                "Actor '%s' receiving report '%s' — running case-creation BT",
                vendor_actor_id,
                request.report_id,
            )

            from py_trees.common import Status

            from vultron.core.behaviors.bridge import BTBridge
            from vultron.core.behaviors.case.receive_report_case_tree import (
                create_receive_report_case_tree,
            )

            bridge = BTBridge(datalayer=self._dl)
            tree = create_receive_report_case_tree(
                report_id=request.report_id,
                offer_id=request.activity_id,
                finder_actor_id=request.actor_id,
            )
            result = bridge.execute_with_setup(
                tree, actor_id=vendor_actor_id, activity=request
            )

            if result.status == Status.SUCCESS:
                logger.info(
                    "✓ Case creation at RM.RECEIVED succeeded for report: %s",
                    request.report_id,
                )
            elif result.status == Status.FAILURE:
                logger.error(
                    "✗ Case creation at RM.RECEIVED failed for report: "
                    "%s — %s",
                    request.report_id,
                    result.feedback_message,
                )
                for err in result.errors or []:
                    logger.error("  - %s", err)
            else:
                logger.warning(
                    "⚠ Case creation at RM.RECEIVED incomplete for report: "
                    "%s (status=%s)",
                    request.report_id,
                    result.status,
                )


class ValidateReportReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: ValidateReportReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: ValidateReportReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        actor_id = request.actor_id
        report_id = request.report_id
        offer_id = request.offer_id
        if report_id is None or offer_id is None:
            raise VultronValidationError(
                "ValidateReportReceivedEvent requires report_id and offer_id"
            )

        case = self._dl.find_case_by_report_id(report_id)
        case_id: str | None = None
        if is_case_model(case):
            case_id = case.id_
        else:
            logger.warning(
                "ValidateReportReceivedUseCase: no case found for report "
                "'%s' — RM state will not be updated in participant record",
                report_id,
            )

        logger.info(
            "Actor '%s' validates VulnerabilityReport '%s'",
            actor_id,
            report_id,
        )

        ValidateCaseUseCase(
            dl=self._dl,
            actor_id=actor_id,
            report_id=report_id,
            offer_id=offer_id,
            case_id=case_id,
        ).execute()


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
            "Actor '%s' tentatively rejects offer '%s' of "
            "VulnerabilityReport '%s'",
            actor_id,
            request.offer_id,
            request.report_id,
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

        if request.report_id:
            case = self._dl.find_case_by_report_id(request.report_id)
            if is_case_model(case):
                InvalidateCaseUseCase(self._dl, case.id_, actor_id).execute()
            else:
                logger.warning(
                    "InvalidateReportReceivedUseCase: no case found for "
                    "report '%s' — RM state not updated",
                    request.report_id,
                )


class AckReportReceivedUseCase:
    def __init__(self, dl: DataLayer, request: AckReportReceivedEvent) -> None:
        self._dl = dl
        self._request: AckReportReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.info(
            "Actor '%s' acknowledges receipt of offer '%s' of "
            "VulnerabilityReport '%s'",
            request.actor_id,
            request.offer_id,
            request.report_id,
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
            request.offer_id,
            request.report_id,
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

        if request.report_id:
            case = self._dl.find_case_by_report_id(request.report_id)
            if is_case_model(case):
                CloseCaseUseCase(self._dl, case.id_, actor_id).execute()
            else:
                logger.warning(
                    "CloseReportReceivedUseCase: no case found for report "
                    "'%s' — RM state not updated",
                    request.report_id,
                )
