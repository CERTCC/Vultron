"""Received use cases for a report's RM moves: validate, invalidate, ack, close."""

import logging
from typing import TYPE_CHECKING, ClassVar

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.report.nodes.conditions import (
    CheckRMStateValid,
)
from vultron.core.behaviors.report.received_report_trees import (
    create_ack_report_received_tree,
    create_close_report_received_tree,
    create_invalidate_report_received_tree,
    create_validate_report_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models.events.report import (
    AckReportReceivedEvent,
    CloseReportReceivedEvent,
    InvalidateReportReceivedEvent,
    ValidateReportReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import (
    case_manager_verdict,
    node_succeeded,
    rm_declaration_verdict,
    verdict_from_bt,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)


def _log_refusal(verdict: HandlerResult, activity_id: str) -> HandlerResult:
    if verdict.disposition is HandlerDisposition.REFUSED:
        logger.warning(
            "Refused activity '%s': %s", activity_id, verdict.reason
        )
    return verdict


def _case_id_for_report(
    dl: CasePersistence, report_id: str | None
) -> str | None:
    """Return the id of this store's case for *report_id*, or ``None``.

    A pre-flight read for the tree factories, not a domain mutation
    (CLP-10-005).  ``None`` is a real answer: the receiver may not hold the
    case yet, and the tree then refuses the activity itself.
    """
    if report_id is None:
        return None
    case = dl.find_case_by_report_id(report_id)
    return case.id_ if case is not None else None


class ValidateReportReceivedUseCase:
    # The sender declares its own RM state; only a participant of the case may
    # (HP-01-006, RSH-06-006).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.PARTICIPANT
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: ValidateReportReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: ValidateReportReceivedEvent = request
        self._trigger_activity = trigger_activity
        self._sync_port = sync_port

    def execute(self) -> HandlerResult:
        request = self._request
        sender_actor_id = request.actor_id
        report_id = request.report_id
        offer_id = request.offer_id
        if report_id is None or offer_id is None:
            logger.warning(
                "ValidateReportReceivedUseCase: activity '%s' is missing its"
                " report id or offer id — refusing",
                request.activity_id,
            )
            return HandlerResult.refused(
                "Accept(Offer(VulnerabilityReport)) is missing its report id "
                "or offer id"
            )

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        logger.info(
            "Actor '%s' validates VulnerabilityReport '%s' (receiving='%s')",
            sender_actor_id,
            report_id,
            receiving_actor_id,
        )

        case_id = _case_id_for_report(self._dl, report_id)
        if case_id is None:
            logger.debug(
                "ValidateReportReceivedUseCase: no case found for report '%s'"
                " — the sender guard will refuse the activity",
                report_id,
            )

        tree = create_validate_report_received_tree(
            report_id=report_id,
            offer_id=offer_id,
            sender_actor_id=sender_actor_id,
            case_id=case_id,
            sender_rule=self.sender_entitlement,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )

        verdict = verdict_from_bt(
            tree, result, label="ValidateReportReceivedBT"
        )
        if case_id is not None:
            # Only the CASE_MANAGER records the move (HP-01-005).
            verdict = case_manager_verdict(tree, verdict, self._dl, case_id)
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "ValidateReportReceivedUseCase: refused for report '%s': %s",
                report_id,
                verdict.reason,
            )
            return verdict

        if node_succeeded(tree, CheckRMStateValid):
            # The Selector's idempotency exit (ID-04-004): already VALID.
            return HandlerResult.skipped(
                f"report '{report_id}' already validated for this sender"
            )
        return verdict


class InvalidateReportReceivedUseCase:
    # The sender declares its own RM state; only a participant of the case may
    # (HP-01-006, RSH-06-006).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.PARTICIPANT
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: InvalidateReportReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._trigger_activity = trigger_activity
        self._sync_port = sync_port
        self._request: InvalidateReportReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        # Two different actors, deliberately (RSH-08-001, BT-17-006): the tree
        # *executes* in the receiving actor's store, but the RM write is about
        # the *sender*, ``request.actor_id`` — the activity is an assertion
        # about the sender's state (HP-00-001), which the tree factory reads
        # from the request.
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        # The case the sender guard and the RM adjudication read.
        case_id = _case_id_for_report(self._dl, request.report_id)
        tree = create_invalidate_report_received_tree(
            request,
            case_id=case_id,
            sender_rule=self.sender_entitlement,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )
        verdict = rm_declaration_verdict(
            tree,
            verdict_from_bt(tree, result, label="InvalidateReportReceivedBT"),
            label="InvalidateReportReceivedBT",
        )
        if case_id is not None:
            # Only the CASE_MANAGER records the move (HP-01-005).  With no
            # case the sender guard has already refused.
            verdict = case_manager_verdict(tree, verdict, self._dl, case_id)
        return _log_refusal(verdict, request.activity_id)


class AckReportReceivedUseCase:
    # RK goes from an actor the Offer(VulnerabilityReport) was addressed to, to the
    # reporter, which holds the Offer and checks the sender against it; it is
    # never sent to the CASE_MANAGER (RMB-08-004, RMB-08-005).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.before_case(
        SenderEntitlementKind.NAMED_ACTOR
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: AckReportReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._request: AckReportReceivedEvent = request
        self._sync_port = sync_port

    def execute(self) -> HandlerResult:
        request = self._request

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        tree = create_ack_report_received_tree(
            request, sender_rule=self.sender_entitlement
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )
        return _log_refusal(
            verdict_from_bt(tree, result, label="AckReportReceivedBT"),
            request.activity_id,
        )


class CloseReportReceivedUseCase:
    """Refuse a report closure: no receiver applies one (CM-23-019).

    A report closure is a ``Reject(Offer(VulnerabilityReport))``.

    A report that belongs to a case is held by the case's Case Owner alone,
    and the Case Owner closes the case by ``Leave(VulnerabilityCase)``
    (CM-23-001).  A ``Reject(Offer(VulnerabilityReport))`` for it is the wrong
    closing act from the owner and a message no other sender has a report to
    send, so the declared rule admits no sender on either case side: the
    tree's sender guard refuses every one, and nothing is written, committed
    or sent.
    Before any case exists the receiver holds no case to apply the sender's
    closure to, so the tree refuses the activity as one about a case it does
    not hold (#2255), as it always has.  Either way the outcome stage leaves
    only a receipt stub of what arrived (CLP-10-018).
    """

    # Before any case, the report's receiver closes it to the reporter (the
    # Offer's addressee, RMB-14-004).  Once a case holds the report, no
    # sender may send one to a case actor (CM-23-019): an empty side admits
    # no one, and a sender-guard refusal is owed no answer (HP-01-006).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.before_case(
        SenderEntitlementKind.NAMED_ACTOR
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: CloseReportReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._trigger_activity = trigger_activity
        self._sync_port = sync_port
        self._request: CloseReportReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        tree = create_close_report_received_tree(
            request,
            case_id=_case_id_for_report(self._dl, request.report_id),
            sender_rule=self.sender_entitlement,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        return _log_refusal(
            verdict_from_bt(tree, result, label="CloseReportReceivedBT"),
            request.activity_id,
        )
