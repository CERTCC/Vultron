"""Use cases for vulnerability case activities."""

import logging
from typing import Any, cast

from vultron.core.models.events.case import (
    AddReportToCaseReceivedEvent,
    CloseCaseReceivedEvent,
)
from vultron.core.models.protocols import is_case_model
from vultron.core.models.vultron_types import VultronActivity
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.use_cases._helpers import _as_id

logger = logging.getLogger(__name__)


class AddReportToCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: AddReportToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AddReportToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        report_id = request.report_id
        case_id = request.case_id
        if report_id is None or case_id is None:
            logger.warning("add_report_to_case: missing report_id or case_id")
            return
        case = self._dl.read(case_id)

        if not is_case_model(case):
            logger.warning("add_report_to_case: case '%s' not found", case_id)
            return

        existing_report_ids = [_as_id(r) for r in case.vulnerability_reports]
        if report_id in existing_report_ids:
            logger.info(
                "Report '%s' already in case '%s' — skipping (idempotent)",
                report_id,
                case_id,
            )
            return

        case.vulnerability_reports.append(report_id)
        self._dl.save(case)
        logger.info("Added report '%s' to case '%s'", report_id, case_id)


class CloseCaseReceivedUseCase:
    def __init__(
        self, dl: CaseOutboxPersistence, request: CloseCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CloseCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id

        logger.info("Actor '%s' is closing case '%s'", actor_id, case_id)

        close_activity = VultronActivity(
            type_="Leave",
            actor=actor_id,
            object_=case_id,
        )
        try:
            self._dl.create(close_activity)
            logger.info("Created Leave activity %s", close_activity.id_)
        except ValueError:
            logger.info(
                "Leave activity for case '%s' already exists — skipping (idempotent)",
                case_id,
            )
            return

        actor_obj = self._dl.read(actor_id)
        if actor_obj is not None and hasattr(actor_obj, "outbox"):
            cast(Any, actor_obj).outbox.items.append(close_activity.id_)
            self._dl.save(actor_obj)
            logger.info(
                "Added Leave activity %s to actor %s outbox",
                close_activity.id_,
                actor_id,
            )
        # Queue for delivery via outbox_handler regardless of outbox field
        self._dl.record_outbox_item(actor_id, close_activity.id_)
