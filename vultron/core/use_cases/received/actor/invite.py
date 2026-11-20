"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import TYPE_CHECKING, ClassVar

from vultron.core.behaviors.case.accept_invite_tree import (
    create_accept_invite_actor_to_case_tree,
)
from vultron.core.behaviors.case.invite_actor_to_case_received_tree import (
    create_invite_actor_to_case_received_tree,
    create_reject_invite_actor_to_case_received_tree,
)
from vultron.core.behaviors.case.received_run import (
    closed_sender_reader,
    run_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
    any_of,
)
from vultron.core.models.events.actor import (
    AcceptInviteActorToCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)


class InviteActorToCaseReceivedUseCase:
    """Handle an incoming ``Invite(VulnerabilityCase preview)[target=Actor]`` activity.

    One path for every receiver (CLP-10-005, CLP-10-013): the use case builds
    ``InviteActorToCaseReceivedBT`` and runs it once as the receiving actor.
    The Invite has one wire shape and two senders, which the path the
    receiver is on tells apart (ADR-0199):

    - **The Case Owner's Invite, at the CASE_MANAGER.**  The Owner decides
      whom to invite and sends the CASE_MANAGER its own Invite, with the
      roles, naming the invitee in ``target`` (CM-17-007).  The CASE_MANAGER
      refuses it with the refusal notice, committing nothing, unless the
      sender holds ``CASE_OWNER``, the invitee is neither the CASE_MANAGER
      nor the Owner, is not removed, joined or closed, and the roles are
      grantable.  An admitted Invite is committed as one entry, and the
      CASE_MANAGER sends its own stub Invite to the invitee, crediting the
      Owner (PCR-08-007, CM-24-002, CM-24-020), and commits it in that tree
      (CM-17-006).
    - **The CASE_MANAGER's stub Invite, at the invitee.**  Intake stores the
      Invite idempotently; the commit stays behind the CASE_MANAGER gate and
      skips; the invitee's effect nodes log the receipt (SL-04-006) and
      record the sender as the case's expected CASE_MANAGER (PCR-03-004).
      The invitee creates no case from the stub (MV-10-004): the full case
      arrives in an Announce (MV-10-003).  The sender must be the case's
      CASE_MANAGER (PCR-03-001); an invitee holding only the stub has no
      CASE_MANAGER to compare the sender with, so it records the sender as
      its trust anchor under PCR-03-004.

    A redelivered Invite that intake finds already archived is the benign
    no-op, ``SKIPPED`` (HP-01-014).

    The ``sync_port`` kwarg is injected for every received use case by
    ``with_received_baseline_ports`` so ``CommitCaseLedgerEntryNode`` can fan
    out via ``sync_port`` (SYNC-02-003, #4113).
    """

    # At the CASE_MANAGER the sender is a participant of the case, whose
    # standing to decide (CASE_OWNER) the tree's guard judges so that a
    # refusal is answered (CM-17-007).  Every other receiver takes the stub
    # Invite from the case's CASE_MANAGER alone, including an invitee that
    # does not hold the case yet, on the no-case path that reads the
    # outside-case side (MV-10-004, HP-01-036, PCR-03-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule(
        at_case_manager=any_of(SenderEntitlementKind.PARTICIPANT),
        at_participant=any_of(SenderEntitlementKind.CASE_MANAGER),
        outside_case=any_of(SenderEntitlementKind.CASE_MANAGER),
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: InviteActorToCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        actor_config: ActorConfig | None = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: InviteActorToCaseReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity
        self._actor_config = actor_config

    def execute(self) -> HandlerResult:
        request = self._request
        tree = create_invite_actor_to_case_received_tree(
            case_id=request.case_id,
            invitee_id=request.invitee_id,
            inviter_id=request.actor_id,
            invite_id=request.activity_id,
            offered_roles=request.roles,
            actor_config=self._actor_config,
            sender_rule=self.sender_entitlement,
        )
        return run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label="InviteActorToCaseReceivedBT",
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )


class AcceptInviteActorToCaseReceivedUseCase:
    """The CASE_MANAGER processes
    ``Accept(Invite(VulnerabilityCase preview)[target=Actor])`` from the invitee.

    Delegates all protocol-significant work to
    ``AcceptInviteActorToCaseBT`` via BTBridge.  The BT runs as the
    receiving actor (not the invitee), recording the invitee's participation
    in its own DataLayer without identity spoofing (PCR-08-010).  Those
    effects are the CASE_MANAGER's (PCR-08-009) and sit behind a role gate
    (BT-17-001); any other receiver of a copy refuses (HP-01-005, #3752).

    BT-06-001, BT-15-001: all RM transitions, participant creation, case
    events, and outbox work live in leaf nodes of the BT.
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.INVITEE
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptInviteActorToCaseReceivedEvent,
        sync_port: SyncActivityPort,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: AcceptInviteActorToCaseReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        # The invitee is the reply's sender, never the actor the embedded
        # copy of the Invite names (CM-11-047).
        invitee_id = request.actor_id

        # The reply's sender is the invitee: the tree's sender guard refuses
        # any sender that is not the recorded Invite's invitee, so the
        # participant is never taken from the embedded copy (CM-11-017).
        tree = create_accept_invite_actor_to_case_tree(
            case_id=request.case_id,
            invitee_id=invitee_id,
            invite_id=request.invite_id,
            sender_rule=self.sender_entitlement,
        )
        # An invitee the case already records as closed (its stub Reject was
        # applied) may act on nothing further: its Accept would join a
        # participant whose RM is terminal.  The tree's closed-sender door
        # stops it, with nothing committed or sent, and declares the refusal
        # (CM-23-018, CM-11-015, RMB-14-006, HP-01-003).  A joined invitee's
        # redelivered Accept is a repeat its guard declares, so the runner
        # reads it SKIPPED (CLP-13-001); no handler reader is passed.
        # Admitting the invitee is the CASE_MANAGER's job alone: the tree
        # declares the manager path only, so the path stage refuses any
        # other receiver (HP-01-005, HP-01-039).
        return run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label="AcceptInviteActorToCaseBT",
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )


class RejectInviteActorToCaseReceivedUseCase:
    """The CASE_MANAGER processes
    ``Reject(Invite(VulnerabilityCase preview)[target=Actor])`` from an invitee.

    Commits a canonical ``CaseLedgerEntry`` for the received rejection
    (``("Reject", "Invite")`` in ``_CANONICAL_PAYLOAD_SIGNATURES``) via BTBridge.
    The CASE_MANAGER records that the invitee declined the invitation; any
    other receiver of a copy refuses (HP-01-005).
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.INVITEE
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: RejectInviteActorToCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
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
        tree = create_reject_invite_actor_to_case_received_tree(
            case_id=request.case_id,
            invite_id=request.invite_id,
            invitee_id=request.actor_id or None,
            sender_rule=self.sender_entitlement,
        )
        # A Reject from an invitee the case already records as closed would
        # close it again: the tree's closed-sender door stops it with nothing
        # committed or sent, so it is SKIPPED (CM-23-049, ID-05-003).
        # Recording the decline is the CASE_MANAGER's job alone: the tree
        # declares the manager path only, so the path stage refuses any
        # other receiver, and one that does not hold the case (HP-01-039).
        return run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label="RejectInviteActorToCaseReceivedBT",
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            reader=closed_sender_reader,
        )
