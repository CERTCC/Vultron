"""Use cases for vulnerability report activities."""

import logging
from typing import TYPE_CHECKING

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.models.events.report import (
    AckReportReceivedEvent,
    CloseReportReceivedEvent,
    CreateReportReceivedEvent,
    InvalidateReportReceivedEvent,
    SubmitReportReceivedEvent,
    ValidateReportReceivedEvent,
)
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronValidationError

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

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

    # Per ADR-0035 DL-06-002: capture domain facts from the inbound Offer so
    # the receiver's trigger-side validate/invalidate/close paths can look up
    # the offer record without re-reading the stored wire Offer activity.
    if request.report_id is None:
        return
    offer_to: list[str] = list(request.activity.to or [])
    offer_record = VultronOfferRecord(
        offer_id=request.activity_id,
        report_id=request.report_id,
        offer_actor_id=request.actor_id,
        offer_to=offer_to,
    )
    try:
        dl.create(offer_record)
        logger.info(
            "Stored VultronOfferRecord for offer '%s'", request.activity_id
        )
    except ValueError as e:
        logger.debug(
            "VultronOfferRecord for offer '%s' already exists: %s",
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
    actor_config: "ActorConfig | None" = None,
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
        actor_config=actor_config,
    )
    result = bridge.execute_with_setup(
        tree,
        actor_id=receiving_actor_id,
        activity=request,
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
            create_report_received_tree,
        )

        request = self._request
        tree = create_report_received_tree(request)
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
        actor_config: "ActorConfig | None" = None,
    ) -> None:
        self._dl = dl
        self._request: SubmitReportReceivedEvent = request
        self._trigger_activity = trigger_activity
        self._sync_port = sync_port
        self._actor_config = actor_config

    def execute(self) -> None:
        request = self._request
        # The report and Offer(Report) activity are stored unconditionally so
        # that a receiver with auto_create_case=False still retains the data
        # needed for a subsequent pre-case ACK (Read(Offer(Report))) or an
        # explicit accept/reject decision (CM-15-001).
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

        # Routing-level policy short-circuit: when the receiver opts out of
        # automatic case creation, do not even invoke the case-creation BT.
        # This is a dispatch decision (like the recipient checks above), so a
        # deliberate policy skip is logged at INFO rather than surfacing as a
        # case-creation FAILURE.  The BT also carries an in-tree
        # CheckAutoCaseCreationEnabledNode gate for any caller that invokes the
        # tree directly (CM-15-001, ADR-0015 Option 3).
        if (
            self._actor_config is not None
            and not self._actor_config.auto_create_case
        ):
            logger.info(
                "SubmitReportReceivedUseCase: auto_create_case disabled for "
                "actor '%s' — stored report '%s' and Offer without creating a "
                "case (pre-case ACK path)",
                receiving_actor_id,
                request.report_id,
            )
            return

        _run_submit_report_case_creation(
            self._dl,
            request,
            receiving_actor_id,
            request.report_id,
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            actor_config=self._actor_config,
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
        sender_actor_id = request.actor_id
        report_id = request.report_id
        offer_id = request.offer_id
        if report_id is None or offer_id is None:
            raise VultronValidationError(
                "ValidateReportReceivedEvent requires report_id and offer_id"
            )

        receiving_actor_id = request.receiving_actor_id
        if receiving_actor_id is None:
            logger.debug(
                "ValidateReportReceivedUseCase: receiving_actor_id not set"
                " — skipping (CLP-10-005)"
            )
            return

        logger.info(
            "Actor '%s' validates VulnerabilityReport '%s' (receiving='%s')",
            sender_actor_id,
            report_id,
            receiving_actor_id,
        )

        # Resolve case_id for the guarded-commit subtree (pre-flight lookup,
        # not domain-significant mutation).
        case = self._dl.find_case_by_report_id(report_id)
        case_id = getattr(case, "id_", None)
        if case_id is None:
            logger.debug(
                "ValidateReportReceivedUseCase: no case found for report '%s'"
                " — guarded commit will be skipped",
                report_id,
            )

        from vultron.core.behaviors.report.received_report_trees import (
            create_validate_report_received_tree,
        )

        tree = create_validate_report_received_tree(
            report_id=report_id,
            offer_id=offer_id,
            sender_actor_id=sender_actor_id,
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )

        if result.status != Status.SUCCESS:
            reason = BTBridge.get_failure_reason(tree)
            logger.warning(
                "ValidateReportReceivedUseCase: BT did not succeed for"
                " report '%s': %s",
                report_id,
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
        self,
        dl: CasePersistence,
        request: AckReportReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: AckReportReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> None:
        request = self._request

        receiving_actor_id = request.receiving_actor_id
        if receiving_actor_id is None:
            logger.debug(
                "AckReportReceivedUseCase: receiving_actor_id not set"
                " — skipping (CLP-10-005)"
            )
            return

        # Resolve case_id for the guarded-commit subtree.
        report_id = request.report_id
        case_id: str | None = None
        if report_id is not None:
            case = self._dl.find_case_by_report_id(report_id)
            case_id = getattr(case, "id_", None)

        from vultron.core.behaviors.report.received_report_trees import (
            create_ack_report_received_tree,
        )

        tree = create_ack_report_received_tree(request, case_id=case_id)
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
            sync_port=self._sync_port,
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
