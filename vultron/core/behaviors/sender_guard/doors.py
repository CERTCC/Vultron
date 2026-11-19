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

from vultron.core.behaviors.act_key_scope import unscoped, with_act_keys
from vultron.core.behaviors.act_keys import CASE_ID, SENDER_ID
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.behaviors.role_condition import ActorHoldsRoleInCaseNode
from vultron.core.behaviors.sender_check_context import (
    ClosedSenderCheck,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderClosureNotRecordedNode,
)
from vultron.enums.roles import CVDRole


def closed_sender_guard(
    case_id: str, sender_id: str, *, refusal_label: str | None = None
) -> py_trees.behaviour.Behaviour:
    """The CM-23-018 check that the case does not record the sender's closure.

    Built here, beside the kinds' guards, so no handler names a sender node
    itself (HP-01-007).  It is not a kind: :func:`closed_sender_door` wraps
    it as the door guard the receive-tree factory places, giving it the
    tree's name (*refusal_label*) for an act that would not close the sender,
    so the guard declares the refusal of that act from a closed sender
    (``REFUSED``); a repeated closing act's door declares none, and the
    handler reads it ``SKIPPED``.  The ``CASE_OWNER`` kind's guard composes
    it too, with no label, so a closed owner is refused for that guard's
    own reason (CM-23-018).

    The check reads the case and the sender from ``/case_id`` and
    ``/sender_id``, seeded here (BTND-01-008).
    """
    return with_act_keys(
        SenderClosureNotRecordedNode(refusal_label=refusal_label),
        {CASE_ID: case_id, SENDER_ID: sender_id},
    )


#: holding the closure check inside it.
_CLOSED_SENDER_MARK = "_vultron_closed_sender_check"


def closed_sender_door(
    case_id: str, check: ClosedSenderCheck, tree_name: str
) -> py_trees.behaviour.Behaviour:
    """The closed-sender door guard the receive-tree factory places.

    It fails when the case records the sender's closure (CM-23-018), unless
    *check* lets the Case Owner complete the case's closure and the sender
    is its Case Owner (CM-23-002).  For an act that would not close the
    sender (``check.closes`` false) the guard declares that failure a
    refusal, naming *tree_name* (HP-01-003); for a closing act it declares
    none, and the handler reads the repeat.  :func:`closed_sender_turned_away`
    reads whether a run ended there.
    """
    guard = closed_sender_guard(
        case_id,
        check.sender_id,
        refusal_label=None if check.closes else tree_name,
    )
    door: py_trees.behaviour.Behaviour = guard
    if check.case_owner_completes:
        door = py_trees.composites.Selector(
            name="SenderOpenOrClosingCaseOwner",
            memory=False,
            children=[guard, case_owner_guard(case_id, check.sender_id)],
        )
    setattr(door, _CLOSED_SENDER_MARK, unscoped(guard))
    return door


def closed_sender_turned_away(
    root: py_trees.behaviour.Behaviour,
) -> SenderClosureNotRecordedNode | None:
    """The closed-sender door guard a received tree's run ended at, or ``None``.

    The factory places the door as one child of the tree's root Sequence; the
    run ended there when the first child that failed is that door and its
    check found the sender's closure recorded.  The guard's
    ``feedback_message`` names the sender and the case (CM-23-018).  A guard
    that declares a refusal (:attr:`SenderClosureNotRecordedNode.declared_refusal`)
    refused an act that would not close the sender; one that declares none
    turned away a repeated closing act, which the handler reports
    ``SKIPPED`` (CM-23-049, ID-05-003).
    """
    for child in root.children:
        if child.status is Status.FAILURE:
            guard = getattr(child, _CLOSED_SENDER_MARK, None)
            if (
                isinstance(guard, SenderClosureNotRecordedNode)
                and guard.sender_closed
            ):
                return guard
            return None
    return None


def case_owner_guard(
    case_id: str, sender_id: str
) -> py_trees.behaviour.Behaviour:
    """The ``CASE_OWNER`` role read the closed-sender door asks as its fallback.

    It admits no one: :func:`closed_sender_door` asks it to tell a Case
    Owner's redelivered ``Leave``, whose case closure may still be
    incomplete, from a repeat that changes nothing (CM-23-002, CM-23-018).
    It is the door Selector's last child, so its FAILURE is the tree's
    answer; it reads the role through ``ActorHoldsRoleInCaseNode``, which
    states no refusal, because the handler reports that repeat ``SKIPPED``,
    not ``REFUSED`` (ID-05-003, #5903).
    """
    return with_case_id(
        ActorHoldsRoleInCaseNode(
            actor_id=sender_id,
            role=CVDRole.CASE_OWNER,
            name="SenderHoldsCaseOwner",
        ),
        case_id,
    )
