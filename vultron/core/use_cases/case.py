"""Use cases for vulnerability case activities."""

import logging
from typing import cast

from py_trees.common import Status

from vultron.core.models.events.case import (
    AddReportToCaseReceivedEvent,
    CloseCaseReceivedEvent,
    CreateCaseReceivedEvent,
    DeferCaseReceivedEvent,
    EngageCaseReceivedEvent,
    UpdateCaseReceivedEvent,
)
from vultron.core.models.vultron_types import VultronActivity
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases._helpers import _as_id
from vultron.core.models.protocols import CaseModel

logger = logging.getLogger(__name__)


def _check_participant_embargo_acceptance(
    case: CaseModel, dl: DataLayer
) -> None:
    active_embargo = case.active_embargo
    if active_embargo is None:
        return
    embargo_id = _as_id(active_embargo)
    for actor_id, participant_id in case.actor_participant_index.items():
        participant = dl.read(participant_id)
        if participant is None:
            logger.warning(
                "update_case: could not read participant '%s' for embargo acceptance check",
                participant_id,
            )
            continue
        if not hasattr(participant, "accepted_embargo_ids"):
            continue
        if embargo_id not in participant.accepted_embargo_ids:
            logger.warning(
                "update_case: participant '%s' (actor '%s') has not accepted the active "
                "embargo '%s' — case update will not be broadcast to this participant "
                "(CM-10-004)",
                participant_id,
                actor_id,
                embargo_id,
            )


class CreateCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: CreateCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CreateCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.case.create_tree import (
            create_create_case_tree,
        )

        actor_id = request.actor_id
        case_id = request.case_id

        if request.case is None:
            logger.warning(
                "create_case: no case domain object in event for case '%s'",
                case_id,
            )
            return

        logger.info("Actor '%s' creates case '%s'", actor_id, case_id)

        bridge = BTBridge(datalayer=self._dl)
        tree = create_create_case_tree(
            case_obj=request.case, actor_id=actor_id
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=request
        )

        if result.status != Status.SUCCESS:
            logger.warning(
                "CreateCaseBT did not succeed for actor '%s' / case '%s': %s",
                actor_id,
                case_id,
                result.feedback_message,
            )


class UpdateCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: UpdateCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: UpdateCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id

        stored_case = cast(CaseModel, self._dl.read(case_id))
        if stored_case is None:
            logger.warning(
                "update_case: case '%s' not found in DataLayer — skipping",
                case_id,
            )
            return

        owner_id = _as_id(stored_case.attributed_to)
        if owner_id != actor_id:
            logger.warning(
                "update_case: actor '%s' is not the owner of case '%s' — skipping update",
                actor_id,
                case_id,
            )
            return

        _check_participant_embargo_acceptance(stored_case, self._dl)

        if (
            request.object_type == "VulnerabilityCase"
            and request.case is not None
        ):
            for field in ("name", "summary", "content"):
                value = getattr(request.case, field, None)
                if value is not None:
                    setattr(stored_case, field, value)
            self._dl.save(stored_case)
            logger.info("Actor '%s' updated case '%s'", actor_id, case_id)
        else:
            logger.info(
                "update_case: object for case '%s' is a reference only — no fields to apply",
                case_id,
            )


class EngageCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: EngageCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: EngageCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.report.prioritize_tree import (
            create_engage_case_tree,
        )

        actor_id = request.actor_id
        case_id = request.case_id

        logger.info(
            "Actor '%s' engages case '%s' (RM → ACCEPTED)",
            actor_id,
            case_id,
        )

        bridge = BTBridge(datalayer=self._dl)
        tree = create_engage_case_tree(case_id=case_id, actor_id=actor_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=request
        )

        if result.status != Status.SUCCESS:
            logger.warning(
                "EngageCaseBT did not succeed for actor '%s' / case '%s': %s",
                actor_id,
                case_id,
                result.feedback_message,
            )


class DeferCaseReceivedUseCase:
    def __init__(self, dl: DataLayer, request: DeferCaseReceivedEvent) -> None:
        self._dl = dl
        self._request: DeferCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.report.prioritize_tree import (
            create_defer_case_tree,
        )

        actor_id = request.actor_id
        case_id = request.case_id

        logger.info(
            "Actor '%s' defers case '%s' (RM → DEFERRED)",
            actor_id,
            case_id,
        )

        bridge = BTBridge(datalayer=self._dl)
        tree = create_defer_case_tree(case_id=case_id, actor_id=actor_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=request
        )

        if result.status != Status.SUCCESS:
            logger.warning(
                "DeferCaseBT did not succeed for actor '%s' / case '%s': %s",
                actor_id,
                case_id,
                result.feedback_message,
            )


class AddReportToCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: AddReportToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AddReportToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        report_id = request.report_id
        case_id = request.case_id
        case = cast(CaseModel, self._dl.read(case_id))

        if case is None:
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
    def __init__(self, dl: DataLayer, request: CloseCaseReceivedEvent) -> None:
        self._dl = dl
        self._request: CloseCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id

        logger.info("Actor '%s' is closing case '%s'", actor_id, case_id)

        close_activity = VultronActivity(
            as_type="Leave",
            actor=actor_id,
            as_object=case_id,
        )
        try:
            self._dl.create(close_activity)
            logger.info("Created Leave activity %s", close_activity.as_id)
        except ValueError:
            logger.info(
                "Leave activity for case '%s' already exists — skipping (idempotent)",
                case_id,
            )
            return

        actor_obj = self._dl.read(actor_id)
        if actor_obj is not None and hasattr(actor_obj, "outbox"):
            actor_obj.outbox.items.append(close_activity.as_id)
            self._dl.save(actor_obj)
            logger.info(
                "Added Leave activity %s to actor %s outbox",
                close_activity.as_id,
                actor_id,
            )
        # Queue for delivery via outbox_handler regardless of outbox field
        self._dl.record_outbox_item(actor_id, close_activity.as_id)
