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
(EMB-02-002) is refused and answered with ER: a ``Reject`` of the Invite,
addressed to the sender.  Both handlers run this check before their tree, so
the ER is built here from what the receiver's store holds.

The store keeps an Invite's object by reference: the Invite reads back whole,
as the proposal the ER factory requires, only when the ``EmbargoEvent`` it
names is stored too.  The refusal therefore stores the copy of the terms the
Invite carries, as the tree's intake does on the normal path, and declines to
answer an Invite that names terms the receiver does not hold (ISSUE-4104).
Storing the terms moves no EM or consent state (EP-09-003).
"""

import logging
from typing import TYPE_CHECKING

from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.embargo import (
    InviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.cs import (
    is_pxa_attacks_observed,
    is_pxa_exploit_public,
    is_pxa_public_aware,
)
from vultron.core.use_cases._helpers import (
    _idempotent_create,
    add_activity_to_outbox,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


def _pxa_embargo_ineligible(dl: CasePersistence, case_id: str) -> bool:
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


def queue_pxa_reject(
    dl: CaseOutboxPersistence,
    trigger_activity: "TriggerActivityPort | None",
    *,
    invite_id: str,
    case_id: str,
    actor_id: str,
    recipient_id: str,
    label: str,
) -> None:
    """Queue ER — a ``Reject`` of *invite_id* — from *actor_id* to *recipient_id*.

    The stored Invite must read back whole (its ``EmbargoEvent`` held), which
    is the caller's to establish.  Without a trigger-activity port nothing can
    be built, so the refusal stands without its ER and says so.
    """
    if trigger_activity is None:
        logger.warning(
            "%s: trigger_activity unavailable — ER not emitted for invite"
            " '%s' on case '%s'",
            label,
            invite_id,
            case_id,
        )
        return
    reject_id, _ = trigger_activity.reject_embargo(
        proposal_id=invite_id,
        case_id=case_id,
        actor=actor_id,
        to=[recipient_id],
    )
    add_activity_to_outbox(actor_id, reject_id, dl)


def refuse_pxa_invite(
    dl: CaseOutboxPersistence,
    trigger_activity: "TriggerActivityPort | None",
    request: InviteToEmbargoOnCaseReceivedEvent,
    *,
    case_id: str,
    invite_id: str,
    embargo_id: str,
    receiving_actor_id: str,
) -> HandlerResult:
    """Refuse an EP on a public/exploited/attacked case and emit ER.

    EMB-01-002: MUST NOT process EP when P/X/A is set; MUST emit ER.  The
    Invite and the terms it carries are stored so the ER can be built from
    the stored Invite; an Invite naming terms the receiver does not hold is
    stored and refused without an ER, which could not name the proposal.
    """
    label = "invite_to_embargo_on_case"
    logger.info(
        "%s: P/X/A set on case '%s' — rejecting EP '%s' (EMB-01-002)",
        label,
        case_id,
        invite_id,
    )
    refused = HandlerResult.refused(
        f"EMB-01-002: P/X/A set on case '{case_id}'; embargo proposal rejected"
    )
    if trigger_activity is None:
        queue_pxa_reject(
            dl,
            None,
            invite_id=invite_id,
            case_id=case_id,
            actor_id=receiving_actor_id,
            recipient_id=request.actor_id,
            label=label,
        )
        return refused
    _idempotent_create(
        dl,
        request.activity_type,
        invite_id,
        request.activity,
        "InviteToEmbargoOnCase",
        invite_id,
    )
    if isinstance(request.object_, EmbargoEvent):
        _idempotent_create(
            dl,
            request.object_.type_,
            embargo_id,
            request.object_,
            "EmbargoEvent",
            invite_id,
        )
    if not isinstance(dl.read(embargo_id), EmbargoEvent):
        logger.warning(
            "%s: invite '%s' names embargo '%s' by id only and it is not"
            " held here — ER not emitted for the refusal on case '%s'",
            label,
            invite_id,
            embargo_id,
            case_id,
        )
        return refused
    queue_pxa_reject(
        dl,
        trigger_activity,
        invite_id=invite_id,
        case_id=case_id,
        actor_id=receiving_actor_id,
        recipient_id=request.actor_id,
        label=label,
    )
    return refused
