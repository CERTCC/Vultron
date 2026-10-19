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

"""Received refusal notice: the participant closes its refused assertion.

The CASE_MANAGER answers an assertion a precondition guard refused with one
``Reject`` of it (CLP-02-005, CLP-05-001, ADR-0141).  The participant that
sent it reads the notice here::

    RefusalNoticeReceivedBT (Sequence)
    ├─ IntakeReceivedActivityNode
    ├─ CaseOpenToExternalWrites / ActivityAddressedToReceiverNode
    ├─ <sender guard: the case's CASE_MANAGER only>
    └─ ClearRefusedAssertionNode

Nothing is committed: the notice is about the ledger, not a case event
(CLP-02-013).  The participant writes no case state and re-sends nothing
(CLP-05-001, CLP-06-005).  A notice from anyone but the case's CASE_MANAGER,
or one naming no case this store holds, is refused by the sender guard
(HP-01-006).
"""

import py_trees

from vultron.core.behaviors.case.nodes.refusal_notice import (
    ClearRefusedAssertionNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_check_context import SenderCheckContext
from vultron.core.behaviors.sender_entitlement import SenderRule


def refusal_notice_received_tree(
    *,
    case_id: str | None,
    refused_activity_id: str,
    reason: str | None,
    sender_id: str,
    sender_rule: SenderRule,
) -> ReceivedActivityTree:
    """Build the received refusal-notice tree.

    Args:
        case_id: The case the notice concerns.
        refused_activity_id: The refused activity the notice names.
        reason: The refusing guard's reason, from the notice's ``summary``.
        sender_id: The notice's ``actor``.
        sender_rule: The use case's declared sender rule (HP-01-008).
    """
    effects: list[py_trees.behaviour.Behaviour] = (
        [
            ClearRefusedAssertionNode(
                case_id=case_id,
                refused_activity_id=refused_activity_id,
                reason=reason,
                sender_id=sender_id,
            )
        ]
        if case_id is not None
        else []
    )
    return create_receive_activity_tree(
        name="RefusalNoticeReceivedBT",
        case_id=None,
        sender_rule=sender_rule,
        # A case this store does not hold, or one naming no CASE_MANAGER,
        # refuses the sender rather than passing it (Regime 1, ADR-0087).
        sender_context=SenderCheckContext(
            sender_id=sender_id, case_id=case_id, case_manager_required=True
        ),
        precondition_guards=[],
        replica_effects=effects,
    )


__all__ = ["refusal_notice_received_tree"]
