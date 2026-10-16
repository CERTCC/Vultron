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

"""The one check that an owner's Leave is blocked by a live embargo (CM-23-011).

The CASE_MANAGER makes it on receipt of the Case Owner's
``Leave(VulnerabilityCase)`` and declines the close
(:func:`~vultron.core.behaviors.case.receive_close_case_tree
.create_close_case_received_tree`).  The ``leave-case`` trigger makes the same
check on the leaving actor's own replica before it runs its pre-close step or
sends anything (TRIG-13-003,
:func:`~vultron.core.behaviors.case.leave_case_trigger_tree
.create_leave_case_trigger_tree`).  Both compose the guards built here, so the
two sides cannot drift apart.
"""

import py_trees

from vultron.core.behaviors.embargo.nodes import (
    IsCloseBlockedByActiveEmbargoNode,
    ReadEmStateNode,
)
from vultron.core.behaviors.sender_entitlement import SenderIsCaseOwnerNode


def owner_close_blocked_by_embargo_guards(
    closing_actor_id: str,
    case_id: str,
    result_out: dict[str, object],
) -> list[py_trees.behaviour.Behaviour]:
    """Guards that all succeed iff *closing_actor_id*'s close is embargo-blocked.

    The sequence succeeds when *closing_actor_id* is the case's Case Owner
    and the case has an embargo in force (``active_embargo`` set, EM
    ``ACTIVE`` or ``REVISE``).  Every node is read-only.

    ``ReadEmStateNode`` publishes ``em_before`` for
    ``IsCloseBlockedByActiveEmbargoNode`` (EM-state reads go through
    ``Read*StateNode``, never inline).  EM is derived from the case's embargo
    register (ADR-0122), and an empty register derives ``EM.NONE`` without a
    warning, so the read needs no ``CaseStatus`` precondition.

    Args:
        closing_actor_id: The actor whose close is checked: the Leave's
            sender on receipt, the triggering actor on the trigger side.
        case_id: The case being closed.
        result_out: Mutable dict the EM read writes ``em_before`` into.  Give
            each composed copy its own dict: the copies are distinct nodes.

    Returns:
        The guard nodes, in order, for the caller to compose in a Sequence.
    """
    return [
        SenderIsCaseOwnerNode(
            sender_actor_id=closing_actor_id,
            case_id=case_id,
            name="CheckIsCaseOwnerForClose",
        ),
        ReadEmStateNode(
            case_id=case_id,
            result_out=result_out,
            name="ReadEmStateForCloseGuard",
        ),
        IsCloseBlockedByActiveEmbargoNode(
            case_id=case_id,
            result_out=result_out,
            name="IsCloseBlockedByActiveEmbargo",
        ),
    ]
