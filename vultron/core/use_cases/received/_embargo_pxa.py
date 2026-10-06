#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""The P/X/A refusal of a received embargo proposal or acceptance.

Once the case is public, an exploit is public or attacks are observed, a
received ``Invite(EmbargoEvent)`` (EMB-01-002) or ``Accept`` of one
(EMB-02-002) is refused and answered with ER: a ``Reject`` of the Invite.
Both handlers run this check before their tree, so the ER is built here from
what the receiver's store holds.

The ER goes where an answer to that Invite goes.  The CASE_MANAGER answers the
proposer that sent it; a participant answers the CASE_MANAGER, never a peer
(EP-09-003, PCR-08-001), and only an Invite addressed to it (EP-09-010).

The store keeps an Invite's object by reference, so the refusal stores the copy
of the terms the Invite carries, as the tree's intake does on the normal path,
and the ER is built from the stored Invite.  An Invite that names its terms by
URI only is answered all the same: the ER names the Invite by id and needs no
terms, so the Invite reads back with the URI as its object (ADR-0123).  Storing
the terms moves no EM or consent state (EP-09-003).

An Invite this receiver already answered before the case went public is a
re-delivery: ``pending_embargo_proposal_index`` maps its embargo to it, the
same latch the tree's idempotency guard reads, so it is skipped rather than
contradicted by an ER (HP-01-003).  The ER itself is the record of the refusal: a
``Reject`` with an id derived from the rejecting actor and the Invite, queued by
a node of ``RefuseEmbargoInviteBT``, so a repeated delivery finds it sent and is
skipped (#4140).
"""

import logging
from typing import TYPE_CHECKING

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.refusal_tree import (
    EmbargoInviteNotYetRefusedNode,
    embargo_invite_refusal_tree,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.embargo import (
    InviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.cs import (
    is_pxa_attacks_observed,
    is_pxa_exploit_public,
    is_pxa_public_aware,
)
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
    node_failed,
)
from vultron.errors import VultronNotFoundError

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)

_INVITE_LABEL = "invite_to_embargo_on_case"


def pxa_embargo_ineligible(dl: CasePersistence, case_id: str) -> bool:
    """Return True when P/X/A is set on the case (EMB-01-002, EMB-02-002).

    Reads the case from the DataLayer; returns False (eligible) when the case
    cannot be resolved so normal processing can continue.
    """
    case = dl.read_case(case_id)
    if case is None:
        return False
    pxa_state = case.current_status.pxa.state
    return (
        is_pxa_public_aware(pxa_state)
        or is_pxa_exploit_public(pxa_state)
        or is_pxa_attacks_observed(pxa_state)
    )


def run_pxa_refusal_tree(
    dl: CaseOutboxPersistence,
    trigger_activity: "TriggerActivityPort | None",
    wire_render_port: "WireRenderPort | None",
    sync_port: "SyncActivityPort | None",
    *,
    invite_id: str,
    case_id: str,
    actor_id: str,
    recipient_id: str | None,
    store_invite: bool,
    embargo: EmbargoEvent | None = None,
    answer: bool = True,
    activity: object | None = None,
    label: str,
) -> str | None:
    """Run the refusal tree; return why it did nothing, or ``None`` if it ran.

    The tree does nothing when the ER was already sent (a re-delivery,
    HP-01-003) or when this node is not the replication leader.

    Without a trigger-activity port nothing can be built, so the refusal
    stands without its ER and says so.
    """
    if answer and trigger_activity is None:
        logger.warning(
            "%s: trigger_activity unavailable — ER not emitted by actor '%s'"
            " to '%s' for invite '%s' on case '%s'",
            label,
            actor_id,
            recipient_id,
            invite_id,
            case_id,
        )
        answer = False
    tree = embargo_invite_refusal_tree(
        case_id,
        invite_id,
        recipient_id,
        store_invite=store_invite,
        embargo=embargo,
        answer=answer,
    )
    result = BTBridge(
        datalayer=dl,
        trigger_activity=trigger_activity,
        wire_render_port=wire_render_port,
        sync_port=sync_port,
    ).execute_with_setup(tree=tree, actor_id=actor_id, activity=activity)
    if result.leader_skipped:
        return "not the replication leader"
    if node_failed(tree, EmbargoInviteNotYetRefusedNode):
        return "the ER was already sent (HP-01-003)"
    applied_or_raise(tree, result, label="RefuseEmbargoInviteBT")
    return None


def _invite_er_recipient(
    dl: CasePersistence, case_id: str, receiving_actor_id: str, sender_id: str
) -> str:
    """Return who the ER to a refused Invite is addressed to.

    The CASE_MANAGER answers the proposer that sent the Invite; any other
    actor answers the CASE_MANAGER (EP-09-003, PCR-08-001).  The role is
    never unfilled (CM-24-006), so a case naming no CASE_MANAGER raises.
    """
    case = dl.read_case(case_id)
    manager_id = (
        resolve_case_manager_id(case, dl) if case is not None else None
    )
    if manager_id is None:
        raise VultronNotFoundError("CASE_MANAGER of case", case_id)
    return sender_id if manager_id == receiving_actor_id else manager_id


def refuse_pxa_invite(
    dl: CaseOutboxPersistence,
    trigger_activity: "TriggerActivityPort | None",
    wire_render_port: "WireRenderPort | None",
    sync_port: "SyncActivityPort | None",
    request: InviteToEmbargoOnCaseReceivedEvent,
    *,
    case_id: str,
    invite_id: str,
    embargo_id: str,
    invitee_id: str,
    receiving_actor_id: str,
) -> HandlerResult:
    """Refuse an EP on a public/exploited/attacked case and emit ER.

    EMB-01-002: MUST NOT process EP when P/X/A is set; MUST emit ER.  The
    Invite and the terms it carries are stored so the ER can be built from
    the stored Invite.  No ER is sent for an Invite already answered (skipped) or
    an Invite addressed to another actor (EP-09-010).  An Invite that names its
    terms by URI is answered all the same: the ER names the Invite (ADR-0123).

    Raises:
        VultronNotFoundError: the case names no CASE_MANAGER (CM-24-006).
    """
    case = dl.read_case(case_id)
    if (
        case is not None
        and case.pending_embargo_proposal_index.get(embargo_id) == invite_id
    ):
        logger.info(
            "%s: invite '%s' from actor '%s' was already answered by actor"
            " '%s' — re-delivery on public case '%s' skipped, no ER",
            _INVITE_LABEL,
            invite_id,
            request.actor_id,
            receiving_actor_id,
            case_id,
        )
        return HandlerResult.skipped(
            f"Invite(EmbargoEvent) '{invite_id}' was already answered on case"
            f" '{case_id}'; no ER contradicts that answer (HP-01-003)"
        )
    logger.info(
        "%s: P/X/A set on case '%s' — actor '%s' rejecting EP '%s' from"
        " actor '%s' (EMB-01-002)",
        _INVITE_LABEL,
        case_id,
        receiving_actor_id,
        invite_id,
        request.actor_id,
    )
    reason = (
        f"EMB-01-002: P/X/A set on case '{case_id}'; embargo proposal rejected"
    )
    terms = (
        request.object_ if isinstance(request.object_, EmbargoEvent) else None
    )
    addressed = receiving_actor_id == invitee_id
    if not addressed:
        logger.warning(
            "%s: invite '%s' from actor '%s' is addressed to '%s', not to"
            " receiving actor '%s' — ER not emitted for the refusal on case"
            " '%s' (EP-09-010)",
            _INVITE_LABEL,
            invite_id,
            request.actor_id,
            invitee_id,
            receiving_actor_id,
            case_id,
        )
    answer = addressed
    skipped = run_pxa_refusal_tree(
        dl,
        trigger_activity,
        wire_render_port,
        sync_port,
        invite_id=invite_id,
        case_id=case_id,
        actor_id=receiving_actor_id,
        recipient_id=(
            _invite_er_recipient(
                dl, case_id, receiving_actor_id, request.actor_id
            )
            if answer
            else None
        ),
        store_invite=True,
        embargo=terms,
        answer=answer,
        activity=request,
        label=_INVITE_LABEL,
    )
    if skipped is not None:
        return HandlerResult.skipped(
            f"Invite(EmbargoEvent) '{invite_id}' on case '{case_id}' not"
            f" refused again: {skipped}"
        )
    if not addressed:
        return HandlerResult.refused(
            f"{reason}; no ER sent, the Invite is addressed to"
            f" '{invitee_id}' (EP-09-010)"
        )
    return HandlerResult.refused(reason)
