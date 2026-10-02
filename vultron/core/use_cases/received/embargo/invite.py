"""Received ``Invite(EmbargoEvent)`` (EP, EV) and its invitee and proposer."""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.announce_teardown_tree import (
    invite_to_embargo_on_case_tree,
)
from vultron.core.behaviors.embargo.nodes import (
    EmbargoProposalNotYetRecordedNode,
)
from vultron.core.behaviors.embargo.proposal_index import (
    record_embargo_proposal_index,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.embargo import (
    InviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import same_actor_id
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
    unaddressed_copy_refusal,
)
from vultron.core.use_cases.received._bt_verdict import (
    node_failed,
    verdict_from_bt,
)
from vultron.core.use_cases.received._embargo_pxa import (
    pxa_embargo_ineligible,
    refuse_pxa_invite,
)
from vultron.errors import (
    VultronNotFoundError,
    VultronProtocolViolationError,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


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


def _store_invite_deadline(
    dl: CasePersistence,
    case_id: str,
    actor_id: str,
    rsvp_deadline: datetime,
) -> None:
    """Store RSVP deadline on the invitee's record for lazy invite-expiry detection.

    A proposal addressed to the CASE_MANAGER names it as the sole recipient,
    but the manager adjudicates that Invite and is never its invitee
    (EP-09-010): its record gets no deadline, so the enforcer of invite
    expiry is never the record expiry is evaluated on (CM-28-003).
    """
    case = dl.read_case(case_id)
    if case is None:
        return
    manager_id = resolve_case_manager_id(case, dl)
    if manager_id is None:
        # No enforcer to tell from the invitee (CM-24-006, CM-28-003).
        raise VultronNotFoundError("CASE_MANAGER of case", case_id)
    if same_actor_id(actor_id, manager_id):
        return
    participant_id = case.actor_participant_index.get(actor_id)
    if not participant_id:
        return
    participant = dl.read(participant_id)
    if not isinstance(participant, CaseParticipant):
        return
    if participant.invite_rsvp_deadline == rsvp_deadline:
        return
    participant.invite_rsvp_deadline = rsvp_deadline
    dl.save(participant)


class InviteToEmbargoOnCaseReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: InviteToEmbargoOnCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: InviteToEmbargoOnCaseReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        case_id = request.context_id or ""
        # ``activity_id`` is a required ``NonEmptyString`` on every event.
        invite_id = request.activity_id

        embargo_id = request.object_id
        if not embargo_id:
            logger.warning(
                "invite_to_embargo_on_case: invite '%s' names no embargo",
                invite_id,
            )
            return HandlerResult.refused(
                f"Invite(EmbargoEvent) '{invite_id}' names no embargo"
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
            return HandlerResult.refused(str(exc))

        # Door check before any tree or write, after the shape checks
        # that write nothing: an unaddressed copy is refused (HP-01-005,
        # ADR-0117).
        if (
            refusal := unaddressed_copy_refusal(
                receiving_actor_id, request, label="Invite(EmbargoEvent)"
            )
        ) is not None:
            return refusal

        if case_id and pxa_embargo_ineligible(self._dl, case_id):
            return refuse_pxa_invite(
                self._dl,
                self._trigger_activity,
                request,
                case_id=case_id,
                invite_id=invite_id,
                embargo_id=embargo_id,
                invitee_id=invitee_id,
                receiving_actor_id=receiving_actor_id,
            )

        # Single BT execution under receiving_actor_id (ADR-0022 / CLP-10-005).
        # invitee_id is threaded into the tree as a node constructor arg so
        # only the addressee's store answers the Invite, even when
        # receiving_actor_id != invitee_id.  The tree's two arms are
        # role-gated in-tree (BT-17-001): the CASE_MANAGER adjudicates and
        # relays the proposal of ``proposer_id`` (EP-09-001, EP-09-002); the
        # addressee's replica answers the Invite to the CASE_MANAGER and
        # writes no EM or consent state (EP-09-003).
        tree = invite_to_embargo_on_case_tree(
            case_id=case_id,
            invitee_id=invitee_id,
            invite_id=invite_id,
            embargo_id=embargo_id,
            proposer_id=resolve_proposer_id(request, self._dl),
            embargo=(
                request.object_
                if isinstance(request.object_, EmbargoEvent)
                else None
            ),
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

        verdict = verdict_from_bt(
            tree, result, label="InviteToEmbargoOnCaseBT"
        )
        if verdict.disposition is HandlerDisposition.REFUSED and node_failed(
            tree, EmbargoProposalNotYetRecordedNode
        ):
            # The same Invite, delivered again (CLP-13-001, HP-01-003).
            verdict = HandlerResult.skipped(
                f"invite '{invite_id}' was already applied on case '{case_id}'"
            )
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning("%s (invite '%s')", verdict.reason, invite_id)
            return verdict

        # Record embargo_id → invite_id in core state so accept/reject
        # trigger use cases can correlate without re-reading the Invite wire
        # activity (ADR-0035 DL-06).  A partial replica that holds no copy
        # of the case keeps the Invite and indexes nothing (Regime 2,
        # ADR-0087); CanAnswerEmbargoInviteNode has already warned.
        if case_id and embargo_id and invite_id:
            try:
                record_embargo_proposal_index(
                    self._dl, case_id, embargo_id, invite_id
                )
            except VultronNotFoundError:
                logger.info(
                    "invite '%s': case '%s' not held here — proposal not"
                    " indexed",
                    invite_id,
                    case_id,
                )

        # Store RSVP deadline on the invitee's participant record so
        # detect_and_apply_expiry() can check it without reading the stored
        # invite activity (CM-28, EP-07-001).
        if case_id and request.rsvp_deadline:
            _store_invite_deadline(
                self._dl, case_id, invitee_id, request.rsvp_deadline
            )
        return verdict
