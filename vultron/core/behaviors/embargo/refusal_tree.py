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

"""The ``Reject`` a receiver sends when it refuses an embargo Invite or its Accept.

Once P/X/A is set, a received ``Invite(EmbargoEvent)`` (EMB-01-002) or
``Accept`` of one (EMB-02-004) is refused and answered with a ``Reject`` of
the Invite, the receiver's own answer and not ER (MSM-02-010).
The refusal is a :class:`~vultron.core.behaviors.case.nodes.diversion_stage.Diversion`
of the received tree (CLP-10-026, ADR-0135): its condition is the P/X/A check,
and its effects answer the delivery, so nothing of the admitted path runs and
nothing is committed — a refusal is a decision about a message, not a case
event (CLP-13-001)::

    PxaInviteRefusal (DiversionStage)
    ├─ PxaBarsEmbargoNode                 # P, X or A set on this case
    └─ PxaInviteRefusalAnswer (Sequence)
       ├─ PersistEmbargoEventNode         # Invite only, inline terms
       ├─ ReceiverIsInviteeNode           # Invite only: only the invitee answers
       ├─ RefusalFactoryAvailableNode     # no port: refused, nothing sent
       ├─ EmbargoInviteNotYetRefusedNode  # the Reject is its own record (HP-01-003)
       └─ SendEmbargoProposalRefusalNode / SendEmbargoInviteAnswerNode

It is the receiver's own answer, and where that receiver may be is the host
tree's path declaration, never a second declaration here (HP-01-038): a
participant answers an Invite addressed to it with a ``Reject`` of it to the
CASE_MANAGER, and
the CASE_MANAGER answers the actor that sent it the Invite or the Accept
(EP-09-003, EP-09-010, PCR-08-001).

The Invite tree declares both the manager and the participant-replica path,
so its refusal may run at either, and the ``Reject`` it sends is the
receiver's own act on whichever one.  What makes that sound is the leaf ahead
of the ``Reject``:
:class:`~vultron.core.behaviors.embargo.nodes.pxa_refusal.ReceiverIsInviteeNode`
admits the invitee alone, which is BT-17-008's second arm, so the emit needs
no recorded exemption beside it.  The Accept tree declares the CASE_MANAGER
path alone, so its refusal reaches no other receiver and the declaration is
the guard.

The ``Reject`` is queued by a node of the tree, never by the use case's ``execute()``
(CLP-10-020).
"""

import py_trees

from vultron.core.behaviors.case.nodes.diversion_stage import (
    Diversion,
)
from vultron.core.behaviors.embargo.nodes.cascade import (
    PersistEmbargoEventNode,
)
from vultron.core.behaviors.embargo.nodes.invite_answer import (
    SendEmbargoInviteAnswerNode,
)
from vultron.core.behaviors.embargo.nodes.pxa_refusal import (
    EmbargoInviteNotYetRefusedNode,
    PxaBarsEmbargoNode,
    ReceiverIsInviteeNode,
    RefusalFactoryAvailableNode,
    SendEmbargoProposalRefusalNode,
)
from vultron.core.models.embargo_event import EmbargoEvent

#: The diversion names the two received embargo trees give the refusal.
PXA_INVITE_REFUSAL = "PxaInviteRefusal"
PXA_ACCEPT_REFUSAL = "PxaAcceptRefusal"


def _answer(
    case_id: str, invite_id: str, send: py_trees.behaviour.Behaviour
) -> list[py_trees.behaviour.Behaviour]:
    """The ``Reject`` itself: wired, not sent before, then queued."""
    return [
        RefusalFactoryAvailableNode(case_id=case_id, invite_id=invite_id),
        EmbargoInviteNotYetRefusedNode(invite_id=invite_id),
        send,
    ]


def _pxa_condition(case_id: str, reason: str) -> PxaBarsEmbargoNode:
    """The diversion's condition: P, X or A is set on the case.

    Each refusal builds its own :class:`Diversion` around this, because the
    two answer different activities with different effects: the Invite's
    refusal stores the inline terms and checks the invitee, the Accept's
    answers the accepting actor.  The condition is shared so neither can
    drift on what P/X/A bars (CS-22-001).
    """
    return PxaBarsEmbargoNode(case_id=case_id, reason=reason)


def pxa_invite_refusal(
    *,
    case_id: str,
    invite_id: str,
    invitee_id: str,
    sender_id: str,
    embargo: EmbargoEvent | None,
) -> Diversion:
    """The P/X/A refusal of a received ``Invite(EmbargoEvent)`` (EMB-01-002).

    The terms the Invite carries are stored first; the ``Reject`` is built from
    the body intake archived for the Invite (CLP-10-017, DL-06-006).  Storing the terms
    moves no EM or consent state (EP-09-003).  An Invite naming its terms by
    URI only is answered all the same: the ``Reject`` names the Invite by id
    (ADR-0123).  Only the invitee answers (EP-09-010); any other store keeps
    the Invite's archive and sends nothing.

    Its host tree declares the manager and the participant-replica path, so
    the refusal may run at either; ``ReceiverIsInviteeNode`` ahead of the
    ``Reject`` is what bounds the emit (BT-17-008).

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
                name="SendEmbargoRefusal",
            ),
        )
    )
    return Diversion(
        name=PXA_INVITE_REFUSAL,
        condition=_pxa_condition(
            case_id,
            f"EMB-01-002: P/X/A set on case '{case_id}'; embargo proposal"
            " rejected",
        ),
        effects=tuple(effects),
    )


def pxa_accept_refusal(
    *, case_id: str, invite_id: str, accepting_actor_id: str
) -> Diversion:
    """The P/X/A refusal of a received ``Accept(Invite(EmbargoEvent))``.

    EMB-02-004: the acceptance moves nothing and the receiver answers the
    accepting actor with a ``Reject`` of the Invite, built from the Invite
    the receiver sent and holds.

    Its host tree, the Accept tree, declares the CASE_MANAGER path alone, so
    this refusal runs only there and needs no emit exemption: the
    declaration is the guard (HP-01-038, BT-17-008).

    Args:
        case_id: The case the Invite was for.
        invite_id: The accepted Invite.
        accepting_actor_id: The Accept's sender, to whom the Reject goes.
    """
    return Diversion(
        name=PXA_ACCEPT_REFUSAL,
        condition=_pxa_condition(
            case_id,
            f"EMB-02-004: P/X/A set on case '{case_id}'; embargo acceptance"
            " rejected",
        ),
        effects=tuple(
            _answer(
                case_id,
                invite_id,
                SendEmbargoInviteAnswerNode(
                    case_id=case_id,
                    invite_id=invite_id,
                    accept=False,
                    recipient_id=accepting_actor_id,
                    name="SendEmbargoRefusal",
                ),
            )
        ),
    )


__all__ = [
    "EmbargoInviteNotYetRefusedNode",
    "PXA_ACCEPT_REFUSAL",
    "PXA_INVITE_REFUSAL",
    "pxa_accept_refusal",
    "pxa_invite_refusal",
]
