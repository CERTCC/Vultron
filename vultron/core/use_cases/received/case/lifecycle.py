"""Use cases for vulnerability case activities."""

import logging
from typing import TYPE_CHECKING, ClassVar

import py_trees
from py_trees.common import Status

from vultron.config.actor import ActorConfig
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
    closed_sender_verdict,
    find_named,
    post_close_refusal,
    reference_edit_verdict,
    verdict_from_bt,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import sender_guard_refused

logger = logging.getLogger(__name__)


class AddReportToCaseReceivedUseCase:
    """Attach a received report to the case and commit a canonical ledger entry.

    Only the CASE_MANAGER attaches the report and commits; replicas apply the
    ledger fan-out.  The sender must be the Case Owner; anyone else is
    ``REFUSED`` with the report not attached (CM-30-002).  A report the case
    already lists is ``SKIPPED``.
    """

    # The Case Owner asks the CASE_MANAGER; a participant takes the report
    # from the CASE_MANAGER alone (CM-30-002, PCR-03-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddReportToCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
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
    """Close the case on an owner Leave, or close one participant's handling.

    The sender must hold a participant record on the case whose closure is
    not recorded, or be its Case Owner; a participant replica takes the
    closure from the CASE_MANAGER alone (PCR-03-001).  Any other sender is
    ``REFUSED`` with nothing committed or sent (HP-01-006).  A Leave from a
    sender whose closure the case already records is a repeat of a closing
    act: it is ``SKIPPED``, whatever its activity id, with nothing committed
    or sent (CM-23-018, ID-05-003).  The Case Owner's is the exception: its
    Leave closes the case as well, so its redelivery runs again to complete
    a closure a failed first delivery left part-way (CM-23-002); once the
    case is fully closed, the post-close boundary refuses it (CM-23-013).

    A Leave that arrives after ``case_fully_closed`` is ``REFUSED`` and
    records nothing (CM-23-013); ``actor_config.post_close_reply`` decides
    whether the sender gets ``Reject(Leave(VulnerabilityCase))`` or no reply
    (ADR-0131).
    """

    # A participant leaves through the CASE_MANAGER; a replica takes the
    # closure from the CASE_MANAGER alone (CM-23-001, PCR-03-001).  The Case
    # Owner is named too: once its own closure is recorded it is no longer
    # an open participant, but its redelivered Leave must still complete a
    # case closure a failed first delivery left part-way (CM-23-002).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.CASE_OWNER, SenderEntitlementKind.PARTICIPANT
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: CloseCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        actor_config: ActorConfig | None = None,
    ) -> None:
        self._dl = dl
        self._request: CloseCaseReceivedEvent = request
        self._sync_port = sync_port
        # trigger_activity lets the received-close tree emit an as:Reject when
        # it must decline an owner close during a live embargo (CM-23-011),
        # or answer a late Leave under PostCloseReply.REJECT (CM-23-013).
        self._trigger_activity = trigger_activity
        # actor_config carries post_close_reply, the one policy point for the
        # reply to a Leave after case_fully_closed (ADR-0131).
        self._actor_config = actor_config or ActorConfig()
        # wire_render_port renders each RM closure status (the leaver's and,
        # on owner Leave, the CASE_MANAGER's own) into the canonical ledger
        # snapshots CM-23-001/005 require (CommitRMClosureEntriesNode).
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
            sender_actor_id=request.actor_id,
            receiving_actor_id=receiving_actor_id,
            post_close_reply=self._actor_config.post_close_reply,
            sender_rule=self.sender_entitlement,
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
        if (refusal := post_close_refusal(tree)) is not None:
            # The case is fully closed: nothing was recorded, and the sender
            # got a Reject only under PostCloseReply.REJECT (CM-23-013).
            return refusal
        closed = closed_sender_verdict(
            tree, closes=True, label="Leave(VulnerabilityCase)"
        )
        if closed is not None:
            # A sender already closed repeats a closing act: its effect is in
            # place, so it is SKIPPED whatever its activity id, with nothing
            # committed or sent (CM-23-018, ID-05-003).
            verdict_from_bt(
                tree, result, label="CloseCaseBT"
            )  # raises on error
            logger.info("CloseCaseReceivedUseCase: %s", closed.reason)
            return closed
        if sender_guard_refused(tree):
            # No standing: refused before the close/decline decision, with
            # nothing committed, declined or sent (HP-01-006).
            verdict = verdict_from_bt(tree, result, label="CloseCaseBT")
            logger.warning(
                "CloseCaseReceivedUseCase: Leave of case '%s' refused: %s",
                case_id,
                verdict.reason,
            )
            return verdict
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
