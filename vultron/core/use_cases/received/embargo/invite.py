"""Received ``Invite(EmbargoEvent)`` (EP, EV) and its invitee and proposer."""

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig
    from vultron.core.ports.wire_render import WireRenderPort

import py_trees

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.invite_received_tree import (
    EmbargoInviteFault,
    EmbargoInviteSubjects,
    received_embargo_invite_tree,
)
from vultron.core.behaviors.embargo.nodes import (
    EmbargoProposalNotYetRecordedNode,
)
from vultron.core.behaviors.embargo.nodes.pxa_refusal import (
    ReceiverIsInviteeNode,
)
from vultron.core.behaviors.embargo.refusal_tree import PXA_INVITE_REFUSAL
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.embargo import (
    InviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_EMBARGO_INVITE_WITHOUT_EMBARGO,
    VULTRON_FAILURE_MISROUTED_EMBARGO_INVITE,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    addressee_refusal,
    node_failed,
    pxa_refusal_verdict,
    verdict_from_bt,
)
from vultron.errors import VultronProtocolViolationError

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)

_TREE_LABEL = "InviteToEmbargoOnCaseBT"


def resolve_invitee_id(
    request: InviteToEmbargoOnCaseReceivedEvent, invite_id: str
) -> str:
    """Return the invitee of an ``Invite(EmbargoEvent)``: its sole ``to``.

    The invitee is a *message subject*, read from the message and never from
    the store it reached (ADR-0022, CLP-10-015).  Every emitter sends one
    recipient — a participant to the CASE_MANAGER, the CASE_MANAGER to one
    participant per relayed Invite (EP-09-002) — so an Invite naming none or
    several is a misrouting, refused rather than guessed at (EP-09-010).  The
    recipient is returned in its canonical spelling, so a trailing slash still
    names the actor (#2667), and two spellings of one actor are one recipient.

    Raises:
        VultronProtocolViolationError: ``to`` names no recipient or more
            than one; the message gives the count.
    """
    invitee_id = request.invitee_id
    if invitee_id is None:
        raise VultronProtocolViolationError(
            f"Invite(EmbargoEvent) '{invite_id}' names"
            f" {len(request.to_recipients)} 'to' recipients; its invitee is"
            " its sole recipient, so it is refused as a misrouting"
            " (EP-09-010, OX-08-001)"
        )
    return invitee_id


def resolve_proposer_id(
    request: InviteToEmbargoOnCaseReceivedEvent, dl: CasePersistence
) -> str:
    """Return the actor whose terms a received ``Invite(EmbargoEvent)`` carries.

    The proposer is the Invite's ``actor`` — or its ``attributedTo`` when the
    proposal was itself relayed, since a relayed Invite is sent as the
    CASE_MANAGER with the proposer attributed (CM-24-001, CM-24-002).  The
    CASE_MANAGER adjudicating the proposal records *this* actor's consent to
    the terms (ADR-0093) and excludes it from the relay (EP-09-002).

    Only a relay may attribute: ``attributedTo`` is honoured when the Invite's
    ``actor`` holds ``CVDRole.CASE_MANAGER`` for the case and ignored
    otherwise, so a participant cannot have a third party's consent recorded
    — or that party left out of the Invites — by naming it on its own
    proposal (no identity spoofing on the received side, PCR-08-010).
    """
    attributed_to = request.activity.attributed_to
    if not attributed_to:
        return request.actor_id
    case = dl.read_case(request.context_id) if request.context_id else None
    if case is None:
        logger.warning(
            "invite_to_embargo_on_case: invite '%s' from '%s' attributes its"
            " proposal to '%s', but this store holds no case '%s' to resolve"
            " the CASE_MANAGER from — treating the sender as the proposer",
            request.activity_id,
            request.actor_id,
            attributed_to,
            request.context_id,
        )
        return request.actor_id
    if request.actor_id == resolve_case_manager_id(case, dl):
        return attributed_to
    logger.warning(
        "invite_to_embargo_on_case: invite '%s' from '%s' attributes its"
        " proposal to '%s', but only the CASE_MANAGER relays — treating the"
        " sender as the proposer",
        request.activity_id,
        request.actor_id,
        attributed_to,
    )
    return request.actor_id


class InviteToEmbargoOnCaseReceivedUseCase:
    # A participant proposes to the CASE_MANAGER, which relays the Invite to
    # every other participant (EP-09-001, EP-09-002); a participant takes the
    # relayed Invite from the CASE_MANAGER alone (EP-09-003, PCR-08).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.CASE_MANAGER,
        SenderEntitlementKind.ACTIVE_PARTICIPANT,
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: InviteToEmbargoOnCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        actor_config: "ActorConfig | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: InviteToEmbargoOnCaseReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity
        self._actor_config = actor_config

    def _subjects(
        self, case_id: str, invite_id: str
    ) -> EmbargoInviteSubjects | EmbargoInviteFault:
        """What the Invite names, or the fault that answers it (EP-09-010).

        A well-formed activity that breaks a protocol shape rule is answered
        with ``Create(ProcessingFault)`` (MSM-05-001); the fault is the
        tree's to send.
        """
        request = self._request
        embargo_id = request.object_id
        if not embargo_id:
            logger.warning(
                "invite_to_embargo_on_case: invite '%s' names no embargo",
                invite_id,
            )
            return EmbargoInviteFault(
                failure_class=VULTRON_FAILURE_EMBARGO_INVITE_WITHOUT_EMBARGO,
                reason=f"Invite(EmbargoEvent) '{invite_id}' names no embargo",
                addressed=True,
            )
        # The invitee is a subject the message names, not the actor whose
        # replica this is (ADR-0022): the Invite's sole `to` recipient.  An
        # Invite naming none or several is a misrouting, refused before the
        # P/X/A check answers it (EP-09-010, HP-01-005).
        try:
            invitee_id = resolve_invitee_id(request, invite_id)
        except VultronProtocolViolationError as exc:
            logger.warning(
                "invite_to_embargo_on_case: refusing invite '%s' from actor"
                " '%s' at receiving actor '%s': %s",
                invite_id,
                request.actor_id,
                request.receiving_actor_id,
                exc,
            )
            return EmbargoInviteFault(
                failure_class=VULTRON_FAILURE_MISROUTED_EMBARGO_INVITE,
                reason=str(exc),
            )
        return EmbargoInviteSubjects(
            embargo_id=embargo_id,
            invitee_id=invitee_id,
            proposer_id=resolve_proposer_id(request, self._dl),
        )

    def execute(self) -> HandlerResult:
        request = self._request
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        case_id = request.context_id or ""
        # ``activity_id`` is a required ``NonEmptyString`` on every event.
        invite_id = request.activity_id
        subjects = self._subjects(case_id, invite_id)

        # Single BT execution under receiving_actor_id (ADR-0022 / CLP-10-005).
        # The door guards, the P/X/A refusal and both arms are in the tree:
        # the CASE_MANAGER adjudicates and relays the proposal (EP-09-001,
        # EP-09-002); the addressee's replica answers the Invite to the
        # CASE_MANAGER and writes no EM or consent state (EP-09-003).
        tree = received_embargo_invite_tree(
            subjects,
            case_id=case_id,
            invite_id=invite_id,
            sender_actor_id=request.actor_id,
            sender_rule=self.sender_entitlement,
            embargo=(
                request.object_
                if isinstance(request.object_, EmbargoEvent)
                else None
            ),
            actor_config=self._actor_config,
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

        verdict = verdict_from_bt(tree, result, label=_TREE_LABEL)
        if isinstance(subjects, EmbargoInviteFault):
            if verdict.disposition is HandlerDisposition.APPLIED:
                verdict = HandlerResult.refused(subjects.reason)
            elif (refusal := addressee_refusal(tree)) is not None:
                verdict = refusal
        elif verdict.disposition is HandlerDisposition.REFUSED:
            verdict = self._refusal(tree, verdict, case_id, subjects)
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning("%s (invite '%s')", verdict.reason, invite_id)
        # No deadline is stored on receipt: the CASE_MANAGER recorded the one
        # it stamped at its relay's commit, and a replica records that value
        # from the committed entry (CM-28-013).
        return verdict

    def _refusal(
        self,
        tree: py_trees.behaviour.Behaviour,
        verdict: HandlerResult,
        case_id: str,
        subjects: EmbargoInviteSubjects,
    ) -> HandlerResult:
        """The verdict for a run the tree did not admit."""
        invite_id = self._request.activity_id
        if (refusal := addressee_refusal(tree)) is not None:
            return refusal
        if (
            refusal := pxa_refusal_verdict(
                tree,
                PXA_INVITE_REFUSAL,
                f"Invite(EmbargoEvent) '{invite_id}' on case '{case_id}'",
            )
        ) is not None:
            if node_failed(tree, ReceiverIsInviteeNode):
                return HandlerResult.refused(
                    f"{refusal.reason}; no ER sent, the Invite is addressed"
                    f" to '{subjects.invitee_id}' (EP-09-010)"
                )
            return refusal
        if node_failed(tree, EmbargoProposalNotYetRecordedNode):
            # The same Invite, delivered again (CLP-13-001, HP-01-003).
            return HandlerResult.skipped(
                f"invite '{invite_id}' was already applied on case '{case_id}'"
            )
        return verdict
