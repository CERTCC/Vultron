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
from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.ports.datalayer import DataLayer
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import (
    _idempotent_create,
    _report_phase_status_id,
)

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
                logger.warning(
                    "VulnerabilityReport %s already exists: %s",
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

        if request.report_id:
            status = VultronParticipantStatus(
                as_id=_report_phase_status_id(
                    request.actor_id, request.report_id, RM.RECEIVED.value
                ),
                context=request.report_id,
                attributed_to=request.actor_id,
                rm_state=RM.RECEIVED,
            )
            _idempotent_create(
                self._dl,
                "ParticipantStatus",
                status.as_id,
                status,
                "ParticipantStatus (report-phase RM.RECEIVED)",
                request.activity_id,
            )
            logger.info(
                "RM START → RECEIVED for report '%s' (actor '%s')",
                request.report_id,
                request.actor_id,
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
                logger.warning(
                    "VulnerabilityReport %s already exists: %s",
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
                logger.warning(
                    "SubmitReport activity %s already exists: %s",
                    request.activity_id,
                    e,
                )

        if request.report_id:
            status = VultronParticipantStatus(
                as_id=_report_phase_status_id(
                    request.actor_id, request.report_id, RM.RECEIVED.value
                ),
                context=request.report_id,
                attributed_to=request.actor_id,
                rm_state=RM.RECEIVED,
            )
            _idempotent_create(
                self._dl,
                "ParticipantStatus",
                status.as_id,
                status,
                "ParticipantStatus (report-phase RM.RECEIVED)",
                request.activity_id,
            )
            logger.info(
                "RM START → RECEIVED for report '%s' (actor '%s')",
                request.report_id,
                request.actor_id,
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
        report_id = request.report_id
        offer_id = request.offer_id

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
            status = VultronParticipantStatus(
                as_id=_report_phase_status_id(
                    actor_id, request.report_id, RM.INVALID.value
                ),
                context=request.report_id,
                attributed_to=actor_id,
                rm_state=RM.INVALID,
            )
            _idempotent_create(
                self._dl,
                "ParticipantStatus",
                status.as_id,
                status,
                "ParticipantStatus (report-phase RM.INVALID)",
                request.activity_id,
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

        # The report is nested inside the offer: inner_object_id is the report.
        if request.report_id:
            status = VultronParticipantStatus(
                as_id=_report_phase_status_id(
                    request.actor_id,
                    request.report_id,
                    RM.RECEIVED.value,
                ),
                context=request.report_id,
                attributed_to=request.actor_id,
                rm_state=RM.RECEIVED,
            )
            _idempotent_create(
                self._dl,
                "ParticipantStatus",
                status.as_id,
                status,
                "ParticipantStatus (report-phase RM.RECEIVED)",
                request.activity_id,
            )
            logger.info(
                "RM START → RECEIVED for report '%s' (actor '%s')",
                request.report_id,
                request.actor_id,
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
            status = VultronParticipantStatus(
                as_id=_report_phase_status_id(
                    actor_id, request.report_id, RM.CLOSED.value
                ),
                context=request.report_id,
                attributed_to=actor_id,
                rm_state=RM.CLOSED,
            )
            _idempotent_create(
                self._dl,
                "ParticipantStatus",
                status.as_id,
                status,
                "ParticipantStatus (report-phase RM.CLOSED)",
                request.activity_id,
            )
