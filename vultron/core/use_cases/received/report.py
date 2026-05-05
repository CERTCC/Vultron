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
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases.received.case import (
    CloseCaseUseCase,
    InvalidateCaseUseCase,
    ValidateCaseUseCase,
)
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)


def _store_submit_report_dependencies(
    dl: CasePersistence, request: SubmitReportReceivedEvent
) -> None:
    if request.report is not None:
        try:
            dl.create(request.report)
            logger.info(
                "Stored VulnerabilityReport with ID: %s", request.report_id
            )
        except ValueError as e:
            logger.debug(
                "VulnerabilityReport %s already exists (pre-stored by inbox endpoint): %s",
                request.report_id,
                e,
            )

    if request.activity is None:
        return

    try:
        dl.create(request.activity)
        logger.info(
            "Stored SubmitReport activity with ID: %s",
            request.activity_id,
        )
    except ValueError as e:
        logger.debug(
            "SubmitReport activity %s already exists (pre-stored by inbox endpoint): %s",
            request.activity_id,
            e,
        )


def _is_primary_submit_report_recipient(
    request: SubmitReportReceivedEvent, receiving_actor_id: str
) -> bool:
    to_list = (request.activity.to or []) if request.activity else []
    cc_list = (request.activity.cc or []) if request.activity else []

    if to_list and receiving_actor_id in to_list:
        return True
    if cc_list and receiving_actor_id in cc_list:
        logger.warning(
            "SubmitReportReceivedUseCase: cc addressing not supported for "
            "Offer(Report) — discarding activity for report '%s'",
            request.report_id,
        )
        return False

    logger.warning(
        "SubmitReportReceivedUseCase: receiving actor '%s' in neither to nor "
        "cc — discarding activity for report '%s'",
        receiving_actor_id,
        request.report_id,
    )
    return False


def _run_submit_report_case_creation(
    dl: CasePersistence,
    request: SubmitReportReceivedEvent,
    receiving_actor_id: str,
    report_id: str,
) -> None:
    from py_trees.common import Status

    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.case.receive_report_case_tree import (
        create_receive_report_case_tree,
    )

    logger.info(
        "Actor '%s' receiving report '%s' — running case-creation BT",
        receiving_actor_id,
        request.report_id,
    )

    bridge = BTBridge(datalayer=dl)
    tree = create_receive_report_case_tree(
        report_id=report_id,
        offer_id=request.activity_id,
        reporter_actor_id=request.actor_id,
    )
    result = bridge.execute_with_setup(
        tree, actor_id=receiving_actor_id, activity=request
    )

    if result.status == Status.SUCCESS:
        logger.info(
            "✓ Case creation at RM.RECEIVED succeeded for report: %s",
            request.report_id,
        )
        return
    if result.status == Status.FAILURE:
        logger.error(
            "✗ Case creation at RM.RECEIVED failed for report: %s — %s",
            request.report_id,
            result.feedback_message,
        )
        for err in result.errors or []:
            logger.error("  - %s", err)
        return

    logger.warning(
        "⚠ Case creation at RM.RECEIVED incomplete for report: %s (status=%s)",
        request.report_id,
        result.status,
    )


class CreateReportReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: CreateReportReceivedEvent
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
        self, dl: CasePersistence, request: SubmitReportReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: SubmitReportReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _store_submit_report_dependencies(self._dl, request)
        if not request.report_id:
            return

        receiving_actor_id = request.receiving_actor_id
        if receiving_actor_id is None:
            logger.warning(
                "SubmitReportReceivedUseCase: receiving_actor_id not set for "
                "report '%s' — skipping case creation",
                request.report_id,
            )
            return

        if not _is_primary_submit_report_recipient(
            request, receiving_actor_id
        ):
            return

        _run_submit_report_case_creation(
            self._dl, request, receiving_actor_id, request.report_id
        )


class ValidateReportReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: ValidateReportReceivedEvent
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
        self, dl: CasePersistence, request: InvalidateReportReceivedEvent
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
    def __init__(
        self, dl: CasePersistence, request: AckReportReceivedEvent
    ) -> None:
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
        self, dl: CasePersistence, request: CloseReportReceivedEvent
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
