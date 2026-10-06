"""Use cases for vulnerability report activities."""

import logging
from typing import TYPE_CHECKING, ClassVar

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case import receive_report_case_tree
from vultron.core.behaviors.case.nodes import (
    CheckAutoCaseCreationEnabledNode,
    CheckProposalAlreadySentForReport,
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
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import is_addressed_to
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
    node_failed,
    node_succeeded,
    verdict_from_bt,
)
from vultron.errors import (
    VultronAlreadyExistsError,
    VultronBTInternalError,
)

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig
    from vultron.core.models.protocols import PersistableModel
    from vultron.core.ports.datalayer import StorableRecord
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    exempt,
)

logger = logging.getLogger(__name__)


def _store_dependency_idempotently(
    dl: CasePersistence,
    obj: "StorableRecord | PersistableModel",
    obj_id: str | None,
    label: str,
) -> None:
    """Store *obj* unless it is already present, distinguishing "already there".

    ``create()`` raises ``ValueError`` for two unrelated reasons: the id is taken,
    and the object cannot be converted to a storage record at all (no ``type_``,
    or a wire-prefixed one). Catching both and logging "already exists" made a
    malformed object indistinguishable from a benign duplicate — a silent drop of
    the very object the use case exists to persist (ARCH-15-001).

    So presence is checked first, and a ``create()`` failure on something we just
    established was absent is re-raised.
    """
    if obj_id and dl.read(obj_id) is not None:
        logger.debug("%s %s already present — skipping store", label, obj_id)
        return
    dl.create(obj)
    logger.info("Stored %s with ID: %s", label, obj_id)


def _store_submit_report_dependencies(
    dl: CasePersistence, request: SubmitReportReceivedEvent
) -> None:
    if request.report is not None:
        _store_dependency_idempotently(
            dl, request.report, request.report_id, "VulnerabilityReport"
        )

    if request.activity is None:
        return

    try:
        _store_dependency_idempotently(
            dl, request.activity, request.activity_id, "SubmitReport activity"
        )
    except ValueError as e:
        logger.debug(
            "SubmitReport activity %s could not be stored: %s",
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
    except VultronAlreadyExistsError as e:
        logger.debug(
            "VultronOfferRecord for offer '%s' already exists: %s",
            request.activity_id,
            e,
        )


def _not_primary_recipient_reason(
    request: SubmitReportReceivedEvent, receiving_actor_id: str
) -> str | None:
    """Why *receiving_actor_id* must not act on this Offer, or ``None``.

    Only a ``to`` recipient acts on an ``Offer(Report)`` (HP-09-001,
    HP-09-002).  Anyone else received a copy that is not addressed to it,
    which it refuses (HP-01-005): the sender addressed the wrong party, and
    the receiver's own record says so rather than reporting a processed
    no-op.
    """
    to_list = (request.activity.to or []) if request.activity else []
    cc_list = (request.activity.cc or []) if request.activity else []

    if is_addressed_to(receiving_actor_id, to_list):
        return None
    if is_addressed_to(receiving_actor_id, cc_list):
        logger.warning(
            "SubmitReportReceivedUseCase: cc addressing not supported for "
            "Offer(Report) — discarding activity for report '%s'",
            request.report_id,
        )
        return "receiving actor is only in cc; cc addressing not supported"

    logger.warning(
        "SubmitReportReceivedUseCase: receiving actor '%s' in neither to nor "
        "cc — discarding activity for report '%s'",
        receiving_actor_id,
        request.report_id,
    )
    return "receiving actor is not a recipient of the Offer"


def _run_submit_report_case_creation(
    dl: CasePersistence,
    request: SubmitReportReceivedEvent,
    receiving_actor_id: str,
    report_id: str,
    trigger_activity: "TriggerActivityPort | None" = None,
    sync_port: "SyncActivityPort | None" = None,
    actor_config: "ActorConfig | None" = None,
    wire_render_port: "WireRenderPort | None" = None,
) -> HandlerResult:
    """Run the receiver-side proposal BT and classify its outcome (#2255).

    The report is already stored, so nothing in this BT judges the sender's
    message: a disabled ``auto_create_case`` gate and an already-sent proposal
    are no-ops, and any other failure is this actor's own (a missing port, a
    CaseActor that cannot be hosted), so it raises rather than refuses.
    """
    logger.info(
        "Actor '%s' receiving report '%s' — running case-creation BT",
        receiving_actor_id,
        request.report_id,
    )

    bridge = BTBridge(
        datalayer=dl,
        trigger_activity=trigger_activity,
        sync_port=sync_port,
        wire_render_port=wire_render_port,
    )
    tree = receive_report_case_tree.create_receive_report_case_tree(
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

    if node_failed(tree, CheckAutoCaseCreationEnabledNode):
        return HandlerResult.skipped("auto_create_case disabled")
    verdict = verdict_from_bt(tree, result, label="ReceiveReportCaseBT")
    if verdict.disposition is HandlerDisposition.REFUSED:
        for err in result.errors or []:
            logger.error("  - %s", err)
        raise VultronBTInternalError(
            f"case proposal for report '{report_id}' failed: {verdict.reason}"
        )
    if node_succeeded(tree, CheckProposalAlreadySentForReport):
        return HandlerResult.skipped(
            f"case proposal for report '{report_id}' already sent"
        )
    if verdict.disposition is HandlerDisposition.APPLIED:
        logger.info(
            "✓ Case creation at RM.RECEIVED succeeded for report: %s",
            request.report_id,
        )
    return verdict


def _log_refusal(verdict: HandlerResult, activity_id: str) -> HandlerResult:
    if verdict.disposition is HandlerDisposition.REFUSED:
        logger.warning(
            "Refused activity '%s': %s", activity_id, verdict.reason
        )
    return verdict


class CreateReportReceivedUseCase:
    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4071", "no sender check defined for report creation"
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: CreateReportReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: CreateReportReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        tree = received_report_trees.create_report_received_tree(request)
        bridge = BTBridge(
            datalayer=self._dl,
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
        # The tree only stores the report and the activity; each store step is
        # idempotent and fails only when the DataLayer does.
        return applied_or_raise(tree, result, label="CreateReportReceivedBT")


class SubmitReportReceivedUseCase:
    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4071", "no sender check defined for report submission"
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

        # The report and Offer(Report) activity are stored unconditionally so
        # that a receiver with auto_create_case=False still retains the data
        # needed for a subsequent pre-case ACK (Read(Offer(Report))) or an
        # explicit accept/reject decision (CM-15-001).
        _store_submit_report_dependencies(self._dl, request)
        if not request.report_id:
            return HandlerResult.skipped(
                "Offer carries no report id; nothing to propose a case for"
            )

        refusal_reason = _not_primary_recipient_reason(
            request, receiving_actor_id
        )
        if refusal_reason is not None:
            return HandlerResult.refused(refusal_reason)

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
            return HandlerResult.skipped("auto_create_case disabled")

        return _run_submit_report_case_creation(
            self._dl,
            request,
            receiving_actor_id,
            request.report_id,
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            actor_config=self._actor_config,
            wire_render_port=self._wire_render_port,
        )


class ValidateReportReceivedUseCase:
    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4071", "no sender check defined for report validation"
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

        tree = create_validate_report_received_tree(
            report_id=report_id,
            offer_id=offer_id,
            sender_actor_id=sender_actor_id,
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl,
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
    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4071", "no sender check defined for report invalidation"
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: InvalidateReportReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: InvalidateReportReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        # The *receiving* actor, not the sender (BT-17-005): an inbound
        # activity is applied to the receiver's own replica, so the tree must
        # execute in the receiver's store.  The actor_id is also passed to the
        # tree factory so the subject of the RM write is explicit (BTND-10-005,
        # ADR-0089).
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        tree = create_invalidate_report_received_tree(
            request, actor_id=receiving_actor_id
        )
        bridge = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )
        return _log_refusal(
            verdict_from_bt(tree, result, label="InvalidateReportReceivedBT"),
            request.activity_id,
        )


class AckReportReceivedUseCase:
    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4071",
        "sender is internal echo route (SenderIsExecutingActorNode inside effect node), not an entitlement guard",
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: AckReportReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: AckReportReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        # Resolve case_id for the guarded-commit subtree.
        report_id = request.report_id
        case_id: str | None = None
        if report_id is not None:
            case = self._dl.find_case_by_report_id(report_id)
            case_id = getattr(case, "id_", None)

        tree = create_ack_report_received_tree(request, case_id=case_id)
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
    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4071", "no sender check defined for report closure"
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: CloseReportReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: CloseReportReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        # The *receiving* actor, not the sender (BT-17-005): an inbound
        # activity is applied to the receiver's own replica, so the tree must
        # execute in the receiver's store.  The actor_id is also passed to the
        # tree factory so the subject of the RM write is explicit (BTND-10-005,
        # ADR-0089).
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        tree = create_close_report_received_tree(
            request, actor_id=receiving_actor_id
        )
        bridge = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )
        return _log_refusal(
            verdict_from_bt(tree, result, label="CloseReportReceivedBT"),
            request.activity_id,
        )
