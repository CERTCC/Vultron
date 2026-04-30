"""Use cases for vulnerability case activities."""

import logging
from typing import Any, cast

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
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)
from vultron.core.models.protocols import (
    CaseModel,
    is_case_model,
    is_participant_model,
)
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import _as_id, update_participant_rm_state

logger = logging.getLogger(__name__)


def _check_participant_embargo_acceptance(
    case: CaseModel, dl: CasePersistence
) -> set[str]:
    """Check which participants have not accepted the active embargo.

    Returns a set of actor IDs whose case updates should be withheld per
    CM-10-004 (participants that have not accepted the active embargo).
    """
    excluded: set[str] = set()
    active_embargo = case.active_embargo
    if active_embargo is None:
        return excluded
    embargo_id = _as_id(active_embargo)
    for actor_id, participant_id in case.actor_participant_index.items():
        participant = dl.read(participant_id)
        if participant is None:
            logger.warning(
                "update_case: could not read participant '%s' for embargo acceptance check",
                participant_id,
            )
            continue
        if not is_participant_model(participant):
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
            excluded.add(actor_id)
    return excluded


class CreateCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: CreateCaseReceivedEvent
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
                BTBridge.get_failure_reason(tree),
            )


class UpdateCaseReceivedUseCase:
    def __init__(
        self, dl: CaseOutboxPersistence, request: UpdateCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: UpdateCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        if case_id is None:
            logger.warning("update_case: missing case_id on request")
            return

        stored_case = self._dl.read(case_id)
        if not is_case_model(stored_case):
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

        excluded_actor_ids = _check_participant_embargo_acceptance(
            stored_case, self._dl
        )

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

        self._broadcast_case_update(case_id, stored_case, excluded_actor_ids)

    def _broadcast_case_update(
        self,
        case_id: str,
        case: CaseModel,
        excluded_actor_ids: set[str] | None = None,
    ) -> None:
        """Broadcast an Announce activity for the updated case to participants.

        Implements CM-06-001/CM-06-002: after a case update, the CaseActor MUST
        send an ActivityStreams Announce to each active case participant's inbox.
        Per CM-10-004, participants who have not accepted the active embargo are
        excluded from the broadcast.
        """
        excluded = excluded_actor_ids or set()
        # Locate the CaseActor (type_="Service") associated with this case
        service_records = self._dl.by_type("Service")
        case_actor_id: str | None = None
        for obj_id, data in service_records.items():
            if data.get("context") == case_id:
                case_actor_id = obj_id
                break

        if case_actor_id is None:
            logger.debug(
                "update_case: no CaseActor found for case '%s' — skipping broadcast",
                case_id,
            )
            return

        participant_ids = [
            actor_id
            for actor_id in case.actor_participant_index.keys()
            if actor_id not in excluded
        ]
        if not participant_ids:
            logger.debug(
                "update_case: no eligible participants in case '%s' — skipping broadcast",
                case_id,
            )
            return

        broadcast = VultronActivity(
            type_="Announce",
            actor=case_actor_id,
            object_=case_id,
            to=participant_ids,
        )
        try:
            self._dl.create(broadcast)
        except ValueError:
            logger.debug(
                "update_case: broadcast activity %s already exists — skipping",
                broadcast.id_,
            )
            return

        case_actor_obj = self._dl.read(case_actor_id)
        if case_actor_obj is not None and hasattr(case_actor_obj, "outbox"):
            cast(Any, case_actor_obj).outbox.items.append(broadcast.id_)
            self._dl.save(case_actor_obj)

        # Enqueue for delivery via outbox_handler
        self._dl.record_outbox_item(case_actor_id, broadcast.id_)

        logger.info(
            "update_case: CaseActor '%s' broadcast Announce for case '%s' to %d participants (CM-06-001)",
            case_actor_id,
            case_id,
            len(participant_ids),
        )


class EngageCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: EngageCaseReceivedEvent
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
        if case_id is None:
            logger.warning("engage_case: missing case_id on request")
            return

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
                BTBridge.get_failure_reason(tree),
            )


class DeferCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: DeferCaseReceivedEvent
    ) -> None:
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
        if case_id is None:
            logger.warning("defer_case: missing case_id on request")
            return

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
                BTBridge.get_failure_reason(tree),
            )


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


class InvalidateCaseUseCase:
    """Transition the actor's RM state to INVALID within the given case.

    Called by ``InvalidateReportReceivedUseCase`` after dereferencing
    report_id to case_id (CM-12-005).
    """

    def __init__(
        self, dl: CasePersistence, case_id: str, actor_id: str
    ) -> None:
        self._dl = dl
        self._case_id = case_id
        self._actor_id = actor_id

    def execute(self) -> None:
        success = update_participant_rm_state(
            self._case_id, self._actor_id, RM.INVALID, self._dl
        )
        if success:
            logger.info(
                "RM → INVALID for actor '%s' in case '%s'",
                self._actor_id,
                self._case_id,
            )
        else:
            logger.warning(
                "Failed to set RM.INVALID for actor '%s' in case '%s'",
                self._actor_id,
                self._case_id,
            )


class CloseCaseUseCase:
    """Transition the actor's RM state to CLOSED within the given case.

    Called by ``CloseReportReceivedUseCase`` after dereferencing
    report_id to case_id (CM-12-005).
    """

    def __init__(
        self, dl: CasePersistence, case_id: str, actor_id: str
    ) -> None:
        self._dl = dl
        self._case_id = case_id
        self._actor_id = actor_id

    def execute(self) -> None:
        success = update_participant_rm_state(
            self._case_id, self._actor_id, RM.CLOSED, self._dl
        )
        if success:
            logger.info(
                "RM → CLOSED for actor '%s' in case '%s'",
                self._actor_id,
                self._case_id,
            )
        else:
            logger.warning(
                "Failed to set RM.CLOSED for actor '%s' in case '%s'",
                self._actor_id,
                self._case_id,
            )


class ValidateCaseUseCase:
    """Run the validate-report behavior tree for the given case.

    Called by ``ValidateReportReceivedUseCase`` after dereferencing
    report_id to case_id (CM-12-005).

    After successful BT validation (RM → VALID), auto-cascades to engage the
    case (RM → ACCEPTED) using the default policy of immediate engagement.
    This eliminates the need for a separate manual ``engage-case`` trigger call
    (D5-7-AUTOENG-2).
    """

    def __init__(
        self,
        dl: CasePersistence,
        actor_id: str,
        report_id: str,
        offer_id: str,
        case_id: str | None = None,
    ) -> None:
        self._dl = dl
        self._actor_id = actor_id
        self._report_id = report_id
        self._offer_id = offer_id
        self._case_id = case_id

    def execute(self) -> None:
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.report.validate_tree import (
            create_validate_report_tree,
        )

        logger.info(
            "Actor '%s' validates VulnerabilityReport '%s'%s via BT",
            self._actor_id,
            self._report_id,
            f" (case '{self._case_id}')" if self._case_id else "",
        )

        bridge = BTBridge(datalayer=self._dl)
        tree = create_validate_report_tree(
            report_id=self._report_id,
            offer_id=self._offer_id,
            case_id=self._case_id,
            actor_id=self._actor_id,
        )
        result = bridge.execute_with_setup(tree, actor_id=self._actor_id)

        if result.status == Status.SUCCESS:
            logger.info(
                "✓ BT validation succeeded for report: %s", self._report_id
            )
        elif result.status == Status.FAILURE:
            logger.error(
                "✗ BT validation failed for report: %s — %s",
                self._report_id,
                result.feedback_message,
            )
            for err in result.errors or []:
                logger.error("  - %s", err)
        else:
            logger.warning(
                "⚠ BT validation incomplete for report: %s (status=%s)",
                self._report_id,
                result.status,
            )
