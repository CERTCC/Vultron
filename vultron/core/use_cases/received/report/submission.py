"""Received use cases for a report's ``Create`` and ``Offer`` (submission)."""

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
    CheckOfferNamesReceiverInToNode,
)
from vultron.core.behaviors.report import received_report_trees
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models.events.report import (
    CreateReportReceivedEvent,
    SubmitReportReceivedEvent,
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
    find_node,
    node_failed,
    node_succeeded,
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

logger = logging.getLogger(__name__)


def _submit_report_verdict(
    tree: py_trees.behaviour.Behaviour,
    result: BTExecutionResult,
    request: SubmitReportReceivedEvent,
    receiving_actor_id: str,
) -> HandlerResult:
    """Classify the one ``Offer(VulnerabilityReport)`` tree's outcome (#2255).

    The factory's doors come first: a copy not addressed to the receiver,
    ``cc``-only included, is refused there with nothing kept but its receipt
    stub (HP-01-005, HP-10-001).  An addressed Offer keeps the report, the
    Offer and the offer record and, when it names a report, proposes the
    case.  A report-less Offer, a sender's own copy that names no ``to``
    recipient here (HP-09-001), a disabled ``auto_create_case`` gate and an
    already-sent proposal propose nothing and are ``SKIPPED``, so the Offer
    is archived (CM-15-002, ADR-0154).  Any other failure is this actor's
    own (a missing port, a CaseActor that cannot be hosted), so it raises
    rather than refuses.
    """
    if (refusal := door_refusal(tree)) is not None:
        return refusal
    eligibility = find_node(tree, CheckOfferNamesReceiverInToNode)
    if eligibility is not None and eligibility.not_named_in_to:
        return HandlerResult.skipped(eligibility.feedback_message)
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


class CreateReportReceivedUseCase:
    # A new report precedes any case, so any actor may send one (HP-01-010).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.before_case(
        SenderEntitlementKind.ANY_ACTOR
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: CreateReportReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
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
        # Intake records the activity and the tree stores the report; each step
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
        trigger_activity: TriggerActivityPort | None = None,
        sync_port: SyncActivityPort | None = None,
        actor_config: ActorConfig | None = None,
        wire_render_port: WireRenderPort | None = None,
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
