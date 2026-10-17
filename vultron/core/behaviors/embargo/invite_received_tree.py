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

"""The one received tree of an ``Invite(EmbargoEvent)`` (CLP-10-005).

:func:`received_embargo_invite_tree` is the factory the Invite handler calls.
A well-formed Invite gets
:func:`~vultron.core.behaviors.embargo.announce_teardown_tree.invite_to_embargo_on_case_tree`.
An Invite that names no embargo, or not exactly one ``to`` recipient, cannot
be built into that tree at all: there is no embargo to adjudicate, or no
invitee to answer it (EP-09-010).  It still runs one tree,
:func:`embargo_invite_fault_tree`::

    InviteToEmbargoOnCaseBT (Sequence)
    ├─ IntakeReceivedActivityNode           # the Invite is archived (CLP-10-018)
    ├─ CaseOpenToExternalWrites             # after close nothing is answered
    └─ EmitEmbargoInviteFaultNode           # Create(ProcessingFault), MSM-05-001

No ledger entry is committed and no state changes: the handler reports the
delivery ``REFUSED``.  The fault is the receiver's own answer to the sender.
An Invite that names no embargo is first checked at the addressee door guard,
so a store it was not addressed to answers nothing (HP-01-005); a misrouted
Invite names no single addressee for that check to admit, so its tree has
none.  Neither carries the sender guard.  The emit is covered by :data:`~vultron.core.behaviors.replica_emit_exemptions.EMBARGO_INVITE_FAULT`.
"""

from dataclasses import dataclass

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.addressee import (
    MISROUTED_EMBARGO_INVITE,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.announce_teardown_tree import (
    invite_to_embargo_on_case_tree,
)
from vultron.core.behaviors.embargo.nodes.invite_fault import (
    EmitEmbargoInviteFaultNode,
)
from vultron.core.behaviors.replica_emit_exemptions import (
    EMBARGO_INVITE_FAULT,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.models.embargo_event import EmbargoEvent

__all__ = [
    "EmbargoInviteFault",
    "EmbargoInviteSubjects",
    "embargo_invite_fault_tree",
    "received_embargo_invite_tree",
]


@dataclass(frozen=True)
class EmbargoInviteFault:
    """Why a received Invite cannot be judged, and how it is answered.

    Attributes:
        failure_class: The ``ProcessingFault`` failure class (MSM-05-001).
        reason: The refusal's reason.
        addressed: The Invite names its recipients, so a store it was not
            addressed to refuses it at the addressee door guard and answers
            nothing (HP-01-005); ``False`` for a misrouting, which names no
            single addressee to check, so its tree declares the
            ``MISROUTED_EMBARGO_INVITE`` exemption and answers the fault.
    """

    failure_class: str
    reason: str
    addressed: bool = False


@dataclass(frozen=True)
class EmbargoInviteSubjects:
    """What a well-formed received Invite names (ADR-0022).

    Attributes:
        embargo_id: The proposed ``EmbargoEvent``.
        invitee_id: The Invite's sole ``to`` recipient (EP-09-010).
        proposer_id: Whose terms these are (CM-24-002).
    """

    embargo_id: str
    invitee_id: str
    proposer_id: str


def embargo_invite_fault_tree(
    failure_class: str, case_id: str | None, *, addressed: bool = False
) -> py_trees.composites.Sequence:
    """Build the tree that archives a malformed Invite and answers it.

    Args:
        failure_class: The ``ProcessingFault`` failure class.
        case_id: The case the Invite names, if any; the fault's context.
        addressed: Refuse a copy not addressed to this store before the
            fault, unanswered (HP-01-005); ``False`` declares the
            ``MISROUTED_EMBARGO_INVITE`` exemption.  See
            :class:`EmbargoInviteFault`.
    """
    return create_receive_activity_tree(
        name="EmbargoInviteFaultBT",
        case_id=None,
        addressee_exemption=None if addressed else MISROUTED_EMBARGO_INVITE,
        precondition_guards=[],
        replica_effects=[
            EmitEmbargoInviteFaultNode(
                failure_class=failure_class, case_id=case_id
            )
        ],
        replica_emit_exemption=EMBARGO_INVITE_FAULT,
    )


def received_embargo_invite_tree(
    subjects: EmbargoInviteSubjects | EmbargoInviteFault,
    *,
    case_id: str,
    invite_id: str,
    sender_actor_id: str,
    sender_rule: SenderRule,
    embargo: EmbargoEvent | None = None,
    actor_config: ActorConfig | None = None,
) -> py_trees.behaviour.Behaviour:
    """The one tree a received ``Invite(EmbargoEvent)`` runs.

    Args:
        subjects: What the Invite names, or why it names too little.
        case_id: The case the Invite is for (its ``context``).
        invite_id: The received Invite.
        sender_actor_id: The Invite's ``actor``.
        sender_rule: The use case's declared sender rule (HP-01-008).
        embargo: The inline terms, if the Invite carries them.
        actor_config: The executing CASE_MANAGER's configuration.
    """
    if isinstance(subjects, EmbargoInviteFault):
        return embargo_invite_fault_tree(
            subjects.failure_class,
            case_id or None,
            addressed=subjects.addressed,
        )
    return invite_to_embargo_on_case_tree(
        case_id=case_id,
        invitee_id=subjects.invitee_id,
        invite_id=invite_id,
        embargo_id=subjects.embargo_id,
        proposer_id=subjects.proposer_id,
        sender_actor_id=sender_actor_id,
        sender_rule=sender_rule,
        embargo=embargo,
        actor_config=actor_config,
    )
