"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import TYPE_CHECKING, ClassVar

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.accept_invite_tree import (
    create_accept_invite_actor_to_case_tree,
)
from vultron.core.behaviors.case.invite_actor_to_case_received_tree import (
    create_invite_actor_to_case_received_tree,
    create_reject_invite_actor_to_case_received_tree,
)
from vultron.core.behaviors.case.nodes.invite_participant import (
    CheckInviteeNotAlreadyParticipantNode,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    SenderEntitlementKind,
    exempt,
)
from vultron.core.models.events.actor import (
    AcceptInviteActorToCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    intake_verdict,
    node_failed,
    not_case_manager_refusal,
    verdict_from_bt,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)


class InviteActorToCaseReceivedUseCase:
    """Handle an incoming ``Invite(Actor, CaseStub)`` activity.

    One path for every receiver (CLP-10-005, CLP-10-013): the use case builds
    ``InviteActorToCaseReceivedBT`` and runs it once as the receiving actor.
    The CASE_MANAGER emits the Invite from its own store and commits it in
    the emitting tree, with no ``cc:`` copy to itself (CM-17-006, ADR-0109),
    so the receiver is the invitee.  Intake stores the Invite idempotently;
    the commit stays behind the CASE_MANAGER gate and skips; the invitee's
    effect nodes log the receipt (SL-04-006) and record the sender as the
    case's expected CASE_MANAGER (PCR-03-004).  The invitee creates no case
    from the stub (MV-10-004): the full case arrives in an Announce
    (MV-10-003).

    A redelivered Invite that intake finds already archived is the benign
    no-op, ``SKIPPED`` (HP-01-003).

    The ``sync_port`` kwarg is injected for every received use case by
    ``with_received_baseline_ports`` so ``CommitCaseLedgerEntryNode`` can fan
    out via ``sync_port`` (SYNC-02-002, #4113).
    """

    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4070", "no sender check for actor invite"
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: InviteActorToCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: InviteActorToCaseReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.case_id
        invitee_id = request.object_id
        if not case_id or not invitee_id:
            logger.warning(
                "InviteActorToCase: invite '%s' is missing its case or"
                " invitee — refusing",
                request.activity_id,
            )
            return HandlerResult.refused(
                "Invite is missing its case id or invitee id"
            )

        actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        tree = create_invite_actor_to_case_received_tree(
            case_id=case_id,
            invitee_id=invitee_id,
            inviter_id=request.actor_id,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=actor_id,
            activity=request,
        )
        verdict = intake_verdict(
            tree, result, label="InviteActorToCaseReceivedBT"
        )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "InviteActorToCaseReceivedUseCase: invite '%s' refused: %s",
                request.activity_id,
                verdict.reason,
            )
        return verdict


class AcceptInviteActorToCaseReceivedUseCase:
    """The CASE_MANAGER processes ``Accept(Invite(actor, case))`` from the invitee.

    Delegates all protocol-significant work to
    ``AcceptInviteActorToCaseBT`` via BTBridge.  The BT runs as the
    receiving actor (not the invitee), recording the invitee's participation
    in its own DataLayer without identity spoofing (PCR-08-010).  Those
    effects are the CASE_MANAGER's (PCR-08-009) and sit behind a role gate
    (BT-17-001); any other receiver of a copy refuses (HP-01-005, #3752).

    BT-06-001, BT-15-001: all RM transitions, participant creation, case
    events, and outbox work live in leaf nodes of the BT.
    """

    sender_entitlement: ClassVar[SenderEntitlement] = (
        SenderEntitlementKind.INVITEE
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptInviteActorToCaseReceivedEvent,
        sync_port: SyncActivityPort,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: AcceptInviteActorToCaseReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.case_id
        invite_id = request.invite_id
        if case_id is None or request.invitee_id is None or not invite_id:
            logger.warning(
                "accept_invite_actor_to_case: missing case_id, invitee_id"
                " or invite_id"
            )
            return HandlerResult.refused(
                "Accept(Invite) is missing its case id, invitee id or"
                " Invite id"
            )
        # The invitee is the reply's sender, never the actor the embedded
        # copy of the Invite names (CM-11-017).
        invitee_id = request.actor_id

        # The BT runs as the *receiving* actor: the inbox-stamped
        # receiving_actor_id, else the owner of the store we hold (BT-17-006).
        # It used to fall back to the case's CASE_MANAGER address instead,
        # which ran the tree under a foreign identity whenever the stamp was
        # absent and let the role gate pass for a store that is not the
        # manager's (#3752; the antipattern in notes/case-communication-model.md).
        actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        # The reply's sender is the invitee: the tree's sender guard refuses
        # any sender that is not the recorded Invite's invitee, so the
        # participant is never taken from the embedded copy (CM-11-017).
        tree = create_accept_invite_actor_to_case_tree(
            case_id=case_id,
            invitee_id=invitee_id,
            invite_id=invite_id,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=actor_id,
            activity=request,
        )

        # The idempotency guard fails both for a fully joined invitee (a
        # duplicate, CLP-13-001) and for a case this actor does not hold.
        if node_failed(tree, CheckInviteeNotAlreadyParticipantNode):
            if self._dl.read(case_id) is None:
                verdict = HandlerResult.refused(f"unknown case '{case_id}'")
            else:
                return HandlerResult.skipped(
                    f"'{invitee_id}' already joined case '{case_id}'"
                )
        else:
            verdict = verdict_from_bt(
                tree, result, label="AcceptInviteActorToCaseBT"
            )
            if verdict.disposition is not HandlerDisposition.REFUSED:
                # Admitting the invitee is the CASE_MANAGER's job alone.
                refusal = not_case_manager_refusal(tree, self._dl, case_id)
                if refusal is not None:
                    verdict = refusal
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "accept_invite_actor_to_case: refused invitee '%s' case"
                " '%s': %s",
                invitee_id,
                case_id,
                verdict.reason,
            )
        return verdict


class RejectInviteActorToCaseReceivedUseCase:
    """The CASE_MANAGER processes ``Reject(Invite(actor, case))`` from an invitee.

    Commits a canonical ``CaseLedgerEntry`` for the received rejection
    (``("Reject", "Invite")`` in ``_CANONICAL_PAYLOAD_SIGNATURES``) via BTBridge.
    The CASE_MANAGER records that the invitee declined the invitation; any
    other receiver of a copy refuses (HP-01-005).
    """

    sender_entitlement: ClassVar[SenderEntitlement] = (
        SenderEntitlementKind.INVITEE
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: RejectInviteActorToCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: RejectInviteActorToCaseReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        logger.info(
            "Actor '%s' rejected invitation '%s'",
            request.actor_id,
            request.invite_id,
        )
        case_id = request.case_id or ""
        if not case_id or not request.invite_id:
            logger.warning(
                "RejectInviteActorToCase: missing case_id or invite_id for"
                " invite '%s' — refusing",
                request.invite_id,
            )
            return HandlerResult.refused(
                "Reject(Invite) is missing its case id or Invite id"
            )

        # The store we hold *is* the receiving actor's, so this resolves
        # without scanning for an actor object (ADR-0073).
        actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        tree = create_reject_invite_actor_to_case_received_tree(
            case_id=case_id,
            invite_id=request.invite_id,
            invitee_id=request.actor_id or None,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=actor_id,
            activity=request,
        )
        verdict = verdict_from_bt(
            tree, result, label="RejectInviteActorToCaseReceivedBT"
        )
        if verdict.disposition is not HandlerDisposition.REFUSED:
            # Recording the decline is the CASE_MANAGER's job alone; the gate
            # also reads a case we do not hold as "not the manager".
            refusal = not_case_manager_refusal(tree, self._dl, case_id)
            if refusal is not None:
                verdict = refusal
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "RejectInviteActorToCaseReceivedUseCase: invite '%s' refused:"
                " %s",
                request.invite_id,
                verdict.reason,
            )
        return verdict
