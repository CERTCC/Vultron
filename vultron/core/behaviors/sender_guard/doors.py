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

"""The closed-sender door the receive-tree factory places (CM-23-018,
CM-23-002), and the checks it is built from.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.sender_check_context import (
    ClosedSenderCheck,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderClosureNotRecordedNode,
    SenderIsCaseOwnerNode,
)


def closed_sender_guard(
    case_id: str, sender_id: str
) -> SenderClosureNotRecordedNode:
    """The CM-23-018 check that the case does not record the sender's closure.

    Built here, beside the kinds' guards, so no handler names a sender node
    itself (HP-01-007).  It is not a kind: :func:`closed_sender_door` wraps
    it as the door guard the receive-tree factory places, and the handler
    tells a repeated closing act (``SKIPPED``) from any other act of a closed
    sender (``REFUSED``).  The ``CASE_OWNER`` kind's guard composes it too,
    so a closed owner is refused (CM-23-018).
    """
    return SenderClosureNotRecordedNode(
        case_id=case_id, sender_actor_id=sender_id
    )


#: holding the closure check inside it.
_CLOSED_SENDER_MARK = "_vultron_closed_sender_check"


def closed_sender_door(
    case_id: str, check: ClosedSenderCheck
) -> py_trees.behaviour.Behaviour:
    """The closed-sender door guard the receive-tree factory places.

    It fails when the case records the sender's closure (CM-23-018), unless
    *check* lets the Case Owner complete the case's closure and the sender
    is its Case Owner (CM-23-002).  :func:`closed_sender_turned_away` reads
    whether a run ended there.

    The ``CASE_OWNER`` read is the Selector's **first** arm and the closure
    check its last, so the arm that speaks last is the one whose reason the
    handler reports.  The order is a log-level decision, not a behavioural
    one: the door is the disjunction either way, but as the last arm the
    owner read's FAILURE would be the tree's whole answer
    (:func:`~vultron.core.behaviors.sender_entitlement.failure_is_the_refusal`),
    so it would log a sender refusal at WARNING for a run the handler
    reports ``SKIPPED`` — this door's act closes the case, so a closed
    sender's repeat changes nothing (CM-23-049, ID-05-003).  First, its
    FAILURE picks a branch the closure check can still admit, which is what
    it is, and the line is DEBUG with no refusal wording (SL-03-002,
    SL-03-003, #5917).
    """
    guard = closed_sender_guard(case_id, check.sender_id)
    door: py_trees.behaviour.Behaviour = guard
    if check.case_owner_completes:
        door = py_trees.composites.Selector(
            name="SenderOpenOrClosingCaseOwner",
            memory=False,
            children=[case_owner_guard(case_id, check.sender_id), guard],
        )
    setattr(door, _CLOSED_SENDER_MARK, guard)
    return door


def closed_sender_turned_away(
    root: py_trees.behaviour.Behaviour,
) -> str | None:
    """Why a received tree's run ended at its closed-sender door, or ``None``.

    The factory places the door as one child of the tree's root Sequence; the
    run ended there when the first child that failed is that door and its
    check found the sender's closure recorded.  The reason names the sender
    and the case (CM-23-018); the handler reports a repeated closing act as
    ``SKIPPED`` (CM-23-049, ID-05-003).
    """
    for child in root.children:
        if child.status is Status.FAILURE:
            guard = getattr(child, _CLOSED_SENDER_MARK, None)
            if (
                isinstance(guard, SenderClosureNotRecordedNode)
                and guard.sender_closed
            ):
                return guard.feedback_message
            return None
    return None


def case_owner_guard(
    case_id: str, sender_id: str
) -> py_trees.behaviour.Behaviour:
    """The ``CASE_OWNER`` read the closed-sender door asks first.

    Built here, beside the kinds' guards, so no handler names a sender node
    itself (HP-01-007).  It refuses no one: :func:`closed_sender_door` asks
    it to tell a Case Owner's redelivered ``Leave``, whose case closure may
    still be incomplete, from a repeat that changes nothing (CM-23-002,
    CM-23-018).  Being a read rather than a door is why it is placed ahead
    of the closure check — see :func:`closed_sender_door` (#5917).
    """
    return SenderIsCaseOwnerNode(sender_actor_id=sender_id, case_id=case_id)
