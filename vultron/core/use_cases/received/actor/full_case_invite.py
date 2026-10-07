"""Use cases for the full-case Invite and its three replies (ADR-0121).

After a participant joins, the CASE_MANAGER asks it to judge the case with
``Invite(Actor)[target=VulnerabilityCase]`` (CM-11-010).  The participant
answers ``Accept`` (RV), ``TentativeReject`` (RI) or ``Reject`` (RC), each
carrying its own ledger position (CM-11-011); the CASE_MANAGER refuses a
reply whose position is behind the Invite's floor, or names an entry its
ledger does not hold (CM-11-012).
"""

import logging
from typing import TYPE_CHECKING, ClassVar

import py_trees

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.full_case_invite_trees import (
    create_full_case_invite_reply_received_tree,
    create_invite_actor_to_full_case_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    SenderEntitlementKind,
    exempt,
)
from vultron.core.models.events.actor import (
    AcceptInviteActorToFullCaseReceivedEvent,
    InviteActorToFullCaseReceivedEvent,
    RejectInviteActorToFullCaseReceivedEvent,
    TentativeRejectInviteActorToFullCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    intake_verdict,
    not_case_manager_refusal,
    verdict_from_bt,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)


class InviteActorToFullCaseReceivedUseCase:
    """The invitee receives the full-case ``Invite(Actor)[target=Case]``.

    Intake archives the Invite so the invitee can answer it; the ledger
    position it carries is the floor the reply must reach (CM-11-010).  The
    invitee already holds the case from the Announce, so nothing is created
    from the Invite.
    """

    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4071", "no sender check for the full-case Invite"
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: InviteActorToFullCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.case_id
        invitee_id = request.invitee_id
        if not case_id or not invitee_id:
            logger.warning(
                "InviteActorToFullCase: invite '%s' is missing its case"
                " or invitee — refusing",
                request.activity_id,
            )
            return HandlerResult.refused(
                "Invite is missing its case id or invitee id"
            )
        actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        tree = create_invite_actor_to_full_case_received_tree(
            case_id=case_id,
            invitee_id=invitee_id,
            inviter_id=request.actor_id,
            floor=request.ledger_tail,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(tree=tree, actor_id=actor_id, activity=request)
        return intake_verdict(
            tree, result, label="InviteActorToFullCaseReceivedBT"
        )


class _FullCaseInviteReplyReceivedUseCase:
    """The CASE_MANAGER processes a reply to the full-case Invite.

    Subclasses name the RM state the reply records (CM-11-011).  A reply the
    guard refuses (CM-11-012), or one that reaches an actor that is not the
    case's CASE_MANAGER (HP-01-005), is ``REFUSED`` and writes nothing.
    """

    sender_entitlement: ClassVar[SenderEntitlement] = (
        SenderEntitlementKind.INVITEE
    )
    rm_state: ClassVar[RM]
    tree_name: ClassVar[str]

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: (
            AcceptInviteActorToFullCaseReceivedEvent
            | TentativeRejectInviteActorToFullCaseReceivedEvent
            | RejectInviteActorToFullCaseReceivedEvent
        ),
        sync_port: SyncActivityPort | None = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def _tree(self) -> py_trees.composites.Sequence:
        request = self._request
        assert request.case_id and request.invite_id
        return create_full_case_invite_reply_received_tree(
            name=self.tree_name,
            case_id=request.case_id,
            invite_id=request.invite_id,
            replier_id=request.actor_id,
            position=request.ledger_tail,
            rm_state=self.rm_state,
        )

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.case_id
        if not case_id or not request.invite_id:
            logger.warning(
                "%s: reply '%s' is missing its case or Invite — refusing",
                self.tree_name,
                request.activity_id,
            )
            return HandlerResult.refused(
                "reply is missing its case id or Invite id"
            )
        actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        tree = self._tree()
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(tree=tree, actor_id=actor_id, activity=request)
        verdict = verdict_from_bt(tree, result, label=self.tree_name)
        if verdict.disposition is not HandlerDisposition.REFUSED:
            refusal = not_case_manager_refusal(tree, self._dl, case_id)
            if refusal is not None:
                verdict = refusal
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "%s: reply '%s' from '%s' refused: %s",
                self.tree_name,
                request.activity_id,
                request.actor_id,
                verdict.reason,
            )
        return verdict


class AcceptInviteActorToFullCaseReceivedUseCase(
    _FullCaseInviteReplyReceivedUseCase
):
    """``Accept(full-case Invite)`` — RV, ``RECEIVED → VALID`` (CM-11-011)."""

    rm_state = RM.VALID
    tree_name = "AcceptInviteActorToFullCaseReceivedBT"

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptInviteActorToFullCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        super().__init__(
            dl, request, sync_port, trigger_activity, wire_render_port
        )


class TentativeRejectInviteActorToFullCaseReceivedUseCase(
    _FullCaseInviteReplyReceivedUseCase
):
    """``TentativeReject(full-case Invite)`` — RI, ``RECEIVED → INVALID``."""

    rm_state = RM.INVALID
    tree_name = "TentativeRejectInviteActorToFullCaseReceivedBT"

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: TentativeRejectInviteActorToFullCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        super().__init__(
            dl, request, sync_port, trigger_activity, wire_render_port
        )


class RejectInviteActorToFullCaseReceivedUseCase(
    _FullCaseInviteReplyReceivedUseCase
):
    """``Reject(full-case Invite)`` — RC, ``RECEIVED → CLOSED`` (CM-11-011)."""

    rm_state = RM.CLOSED
    tree_name = "RejectInviteActorToFullCaseReceivedBT"

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RejectInviteActorToFullCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        super().__init__(
            dl, request, sync_port, trigger_activity, wire_render_port
        )
