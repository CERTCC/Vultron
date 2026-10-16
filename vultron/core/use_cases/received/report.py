"""Use cases for vulnerability report activities."""

import logging
from typing import TYPE_CHECKING, ClassVar

import py_trees

from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.case import receive_report_case_tree
from vultron.core.behaviors.case.nodes import (
    CheckAutoCaseCreationEnabledNode,
    CheckProposalAlreadySentForReport,
)
from vultron.core.behaviors.case.nodes.submit_report import (
    CheckOfferAddressedToReceiverNode,
)
from vultron.core.behaviors.report import received_report_trees
from vultron.core.behaviors.report.nodes.conditions import (
    CheckRMStateValid,
)
from vultron.core.behaviors.report.received_report_trees import (
    create_ack_report_received_tree,
    create_close_report_received_tree,
    create_invalidate_report_received_tree,
    create_validate_report_received_tree,
)
from vultron.core.models.events.report import (
    AckReportReceivedEvent,
    CloseReportReceivedEvent,
    CreateReportReceivedEvent,
    InvalidateReportReceivedEvent,
    SubmitReportReceivedEvent,
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
    applied_or_raise,
    door_refusal,
    failure_reason,
    find_node,
    node_failed,
    node_succeeded,
    rm_declaration_verdict,
    verdict_from_bt,
)
from vultron.errors import (
    VultronBTInternalError,
)

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)

logger = logging.getLogger(__name__)


def _submit_report_verdict(
    tree: py_trees.behaviour.Behaviour,
    result: BTExecutionResult,
    request: SubmitReportReceivedEvent,
    receiving_actor_id: str,
) -> HandlerResult:
    """Classify the one ``Offer(Report)`` tree's outcome (#2255).

    The tree keeps the report, the Offer and the offer record, refuses an
    Offer not addressed to the receiver (HP-01-005), and, when the Offer
    names a report, proposes the case.  A report-less Offer, a disabled
    ``auto_create_case`` gate and an already-sent proposal are no-ops, and
    any other failure is this actor's own (a missing port, a CaseActor that
    cannot be hosted), so it raises rather than refuses — except the door
    guards a received tree carries (CM-23-013); this tree's addressee check
    is its own late one (CM-15-002).
    """
    if (refusal := door_refusal(tree)) is not None:
        return refusal
    guard = find_node(tree, CheckOfferAddressedToReceiverNode)
    if guard is not None and guard.misaddressed:
        return HandlerResult.refused(failure_reason(tree, result))
    if node_failed(tree, CheckAutoCaseCreationEnabledNode):
        logger.info(
            "SubmitReportReceivedUseCase: auto_create_case disabled for"
            " actor '%s' — kept report '%s' and Offer without creating a"
            " case (pre-case ACK path)",
            receiving_actor_id,
            request.report_id,
        )
        return HandlerResult.skipped("auto_create_case disabled")
    verdict = verdict_from_bt(tree, result, label="ReceiveReportCaseBT")
    report_id = request.report_id
    if verdict.disposition is HandlerDisposition.REFUSED:
        for err in result.errors or []:
            logger.error("  - %s", err)
        raise VultronBTInternalError(
            f"case proposal for report '{report_id}' failed: {verdict.reason}"
            if report_id
            else f"keeping the report-less Offer failed: {verdict.reason}"
        )
    if verdict.disposition is not HandlerDisposition.APPLIED:
        return verdict
    if not report_id:
        # The tree kept the Offer and went no further.
        return HandlerResult.skipped(
            "Offer carries no report id; nothing to propose a case for"
        )
    if node_succeeded(tree, CheckProposalAlreadySentForReport):
        return HandlerResult.skipped(
            f"case proposal for report '{report_id}' already sent"
        )
    logger.info(
        "✓ Case creation at RM.RECEIVED succeeded for report: %s",
        report_id,
    )
    return verdict


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


class CreateReportReceivedUseCase:
    # A new report precedes any case, so any actor may send one (HP-01-010).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.before_case(
        SenderEntitlementKind.ANY_ACTOR
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: CreateReportReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: CreateReportReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        tree = received_report_trees.create_report_received_tree(request)
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            # The *receiving* actor, not the sender (BT-17-005): an
            # inbound activity is applied to the receiver's own replica,
            # so the tree must execute in the receiver's store.
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        # Intake archives the activity and the tree stores the report; each step
        # is idempotent and fails only when the DataLayer does.
        return applied_or_raise(tree, result, label="CreateReportReceivedBT")


class SubmitReportReceivedUseCase:
    # A new report precedes any case, so any actor may send one (HP-01-010);
    # only its addressing is checked (HP-01-005, HP-09-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.before_case(
        SenderEntitlementKind.ANY_ACTOR
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: SubmitReportReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
        actor_config: "ActorConfig | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: SubmitReportReceivedEvent = request
        self._trigger_activity = trigger_activity
        self._sync_port = sync_port
        self._actor_config = actor_config

    def execute(self) -> HandlerResult:
        request = self._request
        # Resolve the receiver before any write: it raises when no actor owns
        # this store, and a refusal must not leave the report behind (#2667).
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        if request.report_id:
            logger.info(
                "Actor '%s' receiving report '%s' — running case-creation BT",
                receiving_actor_id,
                request.report_id,
            )
        tree = receive_report_case_tree.create_submit_report_received_tree(
            request, actor_config=self._actor_config
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        ).execute_with_setup(
            tree, actor_id=receiving_actor_id, activity=request
        )
        return _submit_report_verdict(
            tree, result, request, receiving_actor_id
        )


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
                "Accept(Offer(Report)) is missing its report id or offer id"
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
        tree = create_invalidate_report_received_tree(
            request,
            case_id=_case_id_for_report(self._dl, request.report_id),
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
        return rm_declaration_verdict(
            tree,
            _log_refusal(
                verdict_from_bt(
                    tree, result, label="InvalidateReportReceivedBT"
                ),
                request.activity_id,
            ),
            label="InvalidateReportReceivedBT",
        )


class AckReportReceivedUseCase:
    # RK goes from an actor the Offer(Report) was addressed to, to the
    # reporter, which holds the Offer and checks the sender against it; it is
    # never sent to the CASE_MANAGER (RMB-08-003, RMB-08-004).
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
    """Refuse a ``Close(Report)``: no receiver applies one (CM-23-019).

    A report that belongs to a case is held by the case's Case Owner alone,
    and the Case Owner closes the case by ``Leave(VulnerabilityCase)``
    (CM-23-001).  A ``Close(Report)`` for it is the wrong closing act from
    the owner and a message no other sender has a report to send, so the
    declared rule admits no sender on either case side: the tree's sender
    guard refuses every one, and nothing is written, committed or sent.
    Before any case exists the receiver holds no case to apply the sender's
    closure to, so the tree refuses the activity as one about a case it does
    not hold (#2255), as it always has.  Either way intake archives what
    arrived first (CLP-10-018).
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
