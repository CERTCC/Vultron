"""Use cases for vulnerability report activities."""

import logging
from typing import TYPE_CHECKING

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes import (
    create_guarded_commit_case_ledger_entry_tree,
)
from vultron.core.models.events.report import (
    AckReportReceivedEvent,
    CloseReportReceivedEvent,
    CreateReportReceivedEvent,
    InvalidateReportReceivedEvent,
    SubmitReportReceivedEvent,
    ValidateReportReceivedEvent,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases.received.actor import _find_case_actor_id
from vultron.core.use_cases.received.case import (
    ValidateCaseUseCase,
)
from vultron.errors import VultronValidationError

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


def _get_server_base_url() -> str:
    """Return the server base URL from config (neutral module)."""
    from vultron.config import get_config

    return get_config().server.base_url


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
    trigger_activity: "TriggerActivityPort | None" = None,
    sync_port: "SyncActivityPort | None" = None,
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

    bridge = BTBridge(
        datalayer=dl,
        trigger_activity=trigger_activity,
        sync_port=sync_port,
    )
    tree = create_receive_report_case_tree(
        report_id=report_id,
        offer_id=request.activity_id,
        reporter_actor_id=request.actor_id,
    )
    result = bridge.execute_with_setup(
        tree,
        actor_id=receiving_actor_id,
        activity=request,
        server_base_url=_get_server_base_url(),
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
        from py_trees.common import Status

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.report.received_report_trees import (
            create_create_report_received_tree,
        )

        request = self._request
        tree = create_create_report_received_tree(request)
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=request.actor_id,
            activity=request,
        )
        if result.status != Status.SUCCESS:
            reason = BTBridge.get_failure_reason(tree)
            logger.warning(
                "CreateReportReceivedBT did not succeed for activity '%s': %s",
                request.activity_id,
                reason or result.feedback_message or "",
            )


class SubmitReportReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: SubmitReportReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: SubmitReportReceivedEvent = request
        self._trigger_activity = trigger_activity
        self._sync_port = sync_port

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
            self._dl,
            request,
            receiving_actor_id,
            request.report_id,
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
        )


class ValidateReportReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: ValidateReportReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: ValidateReportReceivedEvent = request
        self._trigger_activity = trigger_activity
        self._sync_port = sync_port

    def execute(self) -> None:
        request = self._request
        actor_id = request.actor_id
        report_id = request.report_id
        offer_id = request.offer_id
        if report_id is None or offer_id is None:
            raise VultronValidationError(
                "ValidateReportReceivedEvent requires report_id and offer_id"
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
        ).execute()

        # Per ADR-0021 CLP-10-002, CLP-10-003: guarded commit with pre-flight
        # guard. Only the CaseActor should commit a canonical ledger entry for
        # this activity. Non-CaseActors skip the commit entirely.
        receiving_actor_id = request.receiving_actor_id
        if receiving_actor_id is None:
            logger.debug(
                "ValidateReportReceivedUseCase: receiving_actor_id not set"
                " — skipping canonical commit (issue #1026)"
            )
            return

        case = self._dl.find_case_by_report_id(report_id)
        if case is None:
            logger.debug(
                "ValidateReportReceivedUseCase: no case found for report '%s'"
                " — skipping canonical commit",
                report_id,
            )
            return

        case_id = getattr(case, "id_", None)
        if case_id is None:
            logger.debug(
                "ValidateReportReceivedUseCase: case has no id_"
                " — skipping canonical commit"
            )
            return

        case_actor_id = _find_case_actor_id(self._dl, case_id)
        if case_actor_id is None:
            logger.warning(
                "ValidateReportReceivedUseCase: cannot resolve CaseActor for"
                " case '%s' — skipping canonical commit",
                case_id,
            )
            return

        if receiving_actor_id != case_actor_id:
            logger.debug(
                "ValidateReportReceivedUseCase: receiving actor '%s' is not"
                " the CaseActor for case '%s' — skipping canonical commit"
                " (CLP-10-003)",
                receiving_actor_id,
                case_id,
            )
            return

        bridge = BTBridge(
            datalayer=self._dl,
            sync_port=self._sync_port,
        )
        tree = create_guarded_commit_case_ledger_entry_tree(case_id=case_id)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=case_actor_id,
            activity=request,
        )

        if result.status != Status.SUCCESS:
            reason = BTBridge.get_failure_reason(tree)
            logger.warning(
                "ValidateReportReceivedUseCase: guarded commit BT did not"
                " succeed for case '%s': %s",
                case_id,
                reason or result.feedback_message or "",
            )


class InvalidateReportReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: InvalidateReportReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: InvalidateReportReceivedEvent = request

    def execute(self) -> None:
        from py_trees.common import Status

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.report.received_report_trees import (
            create_invalidate_report_received_tree,
        )

        request = self._request
        tree = create_invalidate_report_received_tree(request)
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=request.actor_id,
            activity=request,
        )
        if result.status != Status.SUCCESS:
            reason = BTBridge.get_failure_reason(tree)
            logger.warning(
                "InvalidateReportReceivedBT did not succeed for activity"
                " '%s': %s",
                request.activity_id,
                reason or result.feedback_message or "",
            )


class AckReportReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: AckReportReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AckReportReceivedEvent = request

    def execute(self) -> None:
        from py_trees.common import Status

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.report.received_report_trees import (
            create_ack_report_received_tree,
        )

        request = self._request
        tree = create_ack_report_received_tree(request)
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=request.actor_id,
            activity=request,
        )
        if result.status != Status.SUCCESS:
            reason = BTBridge.get_failure_reason(tree)
            logger.warning(
                "AckReportReceivedBT did not succeed for activity '%s': %s",
                request.activity_id,
                reason or result.feedback_message or "",
            )


class CloseReportReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: CloseReportReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CloseReportReceivedEvent = request

    def execute(self) -> None:
        from py_trees.common import Status

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.report.received_report_trees import (
            create_close_report_received_tree,
        )

        request = self._request
        tree = create_close_report_received_tree(request)
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=request.actor_id,
            activity=request,
        )
        if result.status != Status.SUCCESS:
            reason = BTBridge.get_failure_reason(tree)
            logger.warning(
                "CloseReportReceivedBT did not succeed for activity '%s': %s",
                request.activity_id,
                reason or result.feedback_message or "",
            )
