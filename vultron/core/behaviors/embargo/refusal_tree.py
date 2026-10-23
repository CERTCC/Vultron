#!/usr/bin/env python

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

"""The ER a receiver sends when it refuses an embargo Invite or its Accept.

Once P/X/A is set, a received ``Invite(EmbargoEvent)`` (EMB-01-002) or
``Accept`` of one (EMB-02-002) is refused and answered with ER, a ``Reject`` of
the Invite.  The refusal is a :class:`~vultron.core.behaviors.case.nodes.diversion_stage.Diversion`
of the received tree (CLP-10-026, ADR-0135): its condition is the P/X/A check,
and its effects answer the delivery, so nothing of the admitted path runs and
nothing is committed — a refusal is a decision about a message, not a case
event (CLP-13-001)::

    PxaInviteRefusal (DiversionStage)
    ├─ PxaBarsEmbargoNode                 # P, X or A set on this case
    └─ PxaInviteRefusalAnswer (Sequence)
       ├─ PersistEmbargoEventNode         # Invite only, inline terms
       ├─ ReceiverIsInviteeNode           # Invite only: only the invitee answers
       ├─ ErFactoryAvailableNode          # no port: refused without its ER
       ├─ EmbargoInviteNotYetRefusedNode  # the ER is its own record (HP-01-003)
       └─ SendEmbargoProposalRefusalNode / SendEmbargoInviteAnswerNode

It is the receiver's own answer, so it is a ``RECEIVER`` diversion: a
participant answers an Invite addressed to it with ER to the CASE_MANAGER, and
the CASE_MANAGER answers the actor that sent it the Invite or the Accept
(EP-09-003, EP-09-010, PCR-08-001).  The emit is covered by
:data:`~vultron.core.behaviors.replica_emit_exemptions.EMBARGO_INVITE_REFUSAL`.
The ER is queued by a node of the tree, never by the use case's ``execute()``
(CLP-10-020).
"""

import py_trees

from vultron.core.behaviors.case.nodes.diversion_stage import (
    Diversion,
    DiversionGate,
)
from vultron.core.behaviors.embargo.nodes.cascade import (
    PersistEmbargoEventNode,
)
from vultron.core.behaviors.embargo.nodes.invite_answer import (
    SendEmbargoInviteAnswerNode,
)
from vultron.core.behaviors.embargo.nodes.pxa_refusal import (
    EmbargoInviteNotYetRefusedNode,
    ErFactoryAvailableNode,
    PxaBarsEmbargoNode,
    ReceiverIsInviteeNode,
    SendEmbargoProposalRefusalNode,
)
from vultron.core.behaviors.replica_emit_exemptions import (
    EMBARGO_INVITE_REFUSAL,
)
from vultron.core.models.embargo_event import EmbargoEvent

#: The diversion names the two received embargo trees give the refusal.
PXA_INVITE_REFUSAL = "PxaInviteRefusal"
PXA_ACCEPT_REFUSAL = "PxaAcceptRefusal"


def _answer(
    case_id: str, invite_id: str, send: py_trees.behaviour.Behaviour
) -> list[py_trees.behaviour.Behaviour]:
    """The ER itself: wired, not sent before, then queued."""
    return [
        ErFactoryAvailableNode(case_id=case_id, invite_id=invite_id),
        EmbargoInviteNotYetRefusedNode(invite_id=invite_id),
        send,
    ]


def _pxa_refusal(
    name: str,
    case_id: str,
    reason: str,
    effects: list[py_trees.behaviour.Behaviour],
) -> Diversion:
    """The receiver's diversion: P/X/A set, so *effects* answer with ER."""
    return Diversion(
        name=name,
        condition=PxaBarsEmbargoNode(case_id=case_id, reason=reason),
        effects=tuple(effects),
        gate=DiversionGate.RECEIVER,
        emit_exemption=EMBARGO_INVITE_REFUSAL,
    )


def pxa_invite_refusal(
    *,
    case_id: str,
    invite_id: str,
    invitee_id: str,
    sender_id: str,
    embargo: EmbargoEvent | None,
) -> Diversion:
    """The P/X/A refusal of a received ``Invite(EmbargoEvent)`` (EMB-01-002).

    The terms the Invite carries are stored first; the ER is built from the
    body intake archived for the Invite (CLP-10-017, DL-06-006).  Storing the terms
    moves no EM or consent state (EP-09-003).  An Invite naming its terms by
    URI only is answered all the same: the ER names the Invite by id
    (ADR-0123).  Only the invitee answers (EP-09-010); any other store keeps
    the Invite's archive and sends nothing.

    Args:
        case_id: The case the embargo was proposed for.
        invite_id: The refused Invite.
        invitee_id: The Invite's sole ``to`` recipient.
        sender_id: The Invite's ``actor``, whom the CASE_MANAGER answers.
        embargo: The inline terms, if the Invite carries them.
    """
    effects: list[py_trees.behaviour.Behaviour] = []
    if embargo is not None:
        effects.append(PersistEmbargoEventNode(embargo=embargo))
    effects.append(
        ReceiverIsInviteeNode(invitee_id=invitee_id, invite_id=invite_id)
    )
    effects.extend(
        _answer(
            case_id,
            invite_id,
            SendEmbargoProposalRefusalNode(
                case_id=case_id,
                invite_id=invite_id,
                sender_id=sender_id,
                name="SendEmbargoRefusalER",
            ),
        )
    )
    return _pxa_refusal(
        PXA_INVITE_REFUSAL,
        case_id,
        f"EMB-01-002: P/X/A set on case '{case_id}'; embargo proposal"
        " rejected",
        effects,
    )


def pxa_accept_refusal(
    *, case_id: str, invite_id: str, accepting_actor_id: str
) -> Diversion:
    """The P/X/A refusal of a received ``Accept(Invite(EmbargoEvent))``.

    EMB-02-002: the acceptance moves nothing and the receiver answers the
    accepting actor with ER, built from the Invite the receiver sent and
    holds.

    Args:
        case_id: The case the Invite was for.
        invite_id: The accepted Invite.
        accepting_actor_id: The Accept's sender, to whom the ER goes.
    """
    return _pxa_refusal(
        PXA_ACCEPT_REFUSAL,
        case_id,
        f"EMB-02-002: P/X/A set on case '{case_id}'; embargo acceptance"
        " rejected",
        _answer(
            case_id,
            invite_id,
            SendEmbargoInviteAnswerNode(
                case_id=case_id,
                invite_id=invite_id,
                accept=False,
                recipient_id=accepting_actor_id,
                name="SendEmbargoRefusalER",
            ),
        ),
    )


__all__ = [
    "EmbargoInviteNotYetRefusedNode",
    "PXA_ACCEPT_REFUSAL",
    "PXA_INVITE_REFUSAL",
    "pxa_accept_refusal",
    "pxa_invite_refusal",
]
