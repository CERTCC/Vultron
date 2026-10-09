"""Use cases for vulnerability case activities."""

import logging
from typing import TYPE_CHECKING, ClassVar

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.add_report_received_tree import (
    create_add_report_to_case_received_tree,
)
from vultron.core.behaviors.case.receive_close_case_tree import (
    create_close_case_received_tree,
)
from vultron.core.models.events.case import (
    AddReportToCaseReceivedEvent,
    CloseCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    find_named,
    reference_edit_verdict,
    verdict_from_bt,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    SenderEntitlementKind,
    exempt,
)

logger = logging.getLogger(__name__)


class AddReportToCaseReceivedUseCase:
    """Attach a received report to the case and commit a canonical ledger entry.

    Only the CASE_MANAGER attaches the report and commits; replicas apply the
    ledger fan-out.  The sender must be the Case Owner; anyone else is
    ``REFUSED`` with the report not attached (CM-30-002).  A report the case
    already lists is ``SKIPPED``.
    """

    sender_entitlement: ClassVar[SenderEntitlement] = (
        SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddReportToCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: AddReportToCaseReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        report_id = request.report_id
        case_id = request.case_id
        if report_id is None or case_id is None:
            logger.warning("add_report_to_case: missing report_id or case_id")
            return HandlerResult.refused(
                "Add(Report, Case) is missing its report id or case id"
            )
        if self._dl.read_case(case_id) is None:
            logger.warning("add_report_to_case: case '%s' not found", case_id)
            return HandlerResult.refused(f"unknown case '{case_id}'")

        tree = create_add_report_to_case_received_tree(
            report_id=report_id,
            case_id=case_id,
            sender_id=request.actor_id,
        )
        result = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        verdict = reference_edit_verdict(
            tree,
            verdict_from_bt(
                tree, result, label="GuardedAttachReportAndCommitBT"
            ),
            self._dl,
            case_id,
        )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "add_report_to_case: report '%s' in case '%s' refused: %s",
                report_id,
                case_id,
                verdict.reason,
            )
        return verdict


class CloseCaseReceivedUseCase:
    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4070", "no sender check defined for case closure"
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: CloseCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: CloseCaseReceivedEvent = request
        self._sync_port = sync_port
        # trigger_activity lets the received-close tree emit an as:Reject when
        # it must decline an owner close during a live embargo (CM-23-011).
        self._trigger_activity = trigger_activity
        # wire_render_port renders the CASE_MANAGER's own RM.CLOSED
        # ParticipantStatus into the canonical ledger snapshot CM-23-005
        # requires (CommitCaseActorRMClosedEntryNode, ISSUE-2505).
        self._wire_render_port = wire_render_port

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.case_id
        if case_id is None:
            logger.warning("close_case: missing case_id")
            return HandlerResult.refused(
                "Leave(VulnerabilityCase) has no case id"
            )

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        logger.info(
            "Actor '%s' is closing case '%s'",
            request.actor_id,
            case_id,
        )

        tree = create_close_case_received_tree(
            case_id=case_id,
            activity_id=request.activity_id,
            activity_obj=request.activity,
            sender_actor_id=request.actor_id,
            receiving_actor_id=receiving_actor_id,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )
        if _close_declined(tree):
            # The decline arm ran: the case was left open and the owner was
            # answered with an as:Reject (CM-23-011).  That is a refusal of the
            # close whether or not the Reject itself could be emitted.
            reason = f"close of case '{case_id}' declined: embargo active"
            logger.info("CloseCaseReceivedUseCase: %s (CM-23-011)", reason)
            return HandlerResult.refused(f"{reason} (CM-23-011)")
        verdict = verdict_from_bt(
            _close_arm(tree) or tree, result, label="CloseCaseBT"
        )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "CloseCaseReceivedUseCase: close of case '%s' refused: %s",
                case_id,
                verdict.reason,
            )
        return verdict


def _close_declined(tree: py_trees.behaviour.Behaviour) -> bool:
    """True when the CM-23-011 decline arm decided to decline the close.

    The arm's guards all passing is the decision; the as:Reject emit that
    follows may still fail (no trigger port), which leaves the case just as
    unclosed.
    """
    arm = find_named(tree, "DeclineOwnerCloseIfEmbargoed")
    guard = find_named(arm, "IsCloseBlockedByActiveEmbargo") if arm else None
    return guard is not None and guard.status == Status.SUCCESS


def _close_arm(
    tree: py_trees.behaviour.Behaviour,
) -> py_trees.behaviour.Behaviour | None:
    """The close arm, whose failure names why a non-declined close failed.

    The ``CloseOrDecline`` Selector tries the decline arm last, so on a plain
    failure the decline arm's "not declining" guard is the last failed child;
    the cause is in the close arm (BT-13-001).
    """
    return find_named(tree, "CloseCaseReceive")
