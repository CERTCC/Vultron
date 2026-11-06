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

"""Received-side BT for the CASE_MANAGER's answer on a recommender's inbox.

The recommender's receipt of ``Accept`` or ``Reject`` of its own
``Offer(Actor)[target=VulnerabilityCase]`` (CM-16-006, CM-16-007, CM-16-009).
"""

import py_trees

from vultron.core.behaviors.case.intake_only_received_tree import (
    create_incomplete_activity_received_tree,
)
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderRule,
)
from vultron.core.behaviors.sender_guard import SenderCheckContext


def create_recommendation_answer_received_tree(
    name: str,
    case_id: str | None,
    sender_id: str,
    *,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Received-side BT for the CASE_MANAGER's answer on a recommender's inbox.

    The answer is ``Accept`` or ``Reject`` of the recommender's own
    ``Offer(Actor)[target=VulnerabilityCase]`` (CM-16-006, CM-16-007, CM-16-009).  The
    CASE_MANAGER ledgered it when it sent it (CM-16-010), and the recommender
    takes that entry from the ledger; a participant never commits
    (CLP-09-001), so this receipt records no entry on the CLP-02-013 ground of
    an activity only the CASE_MANAGER sends, received by a participant.

    Tree structure::

        <name> (Sequence, memory=False)
        ├── ActivityAddressedToReceiver    — addressee door guard (HP-01-005)
        ├── ActivityNotSeenBeforeNode      — seen-before door
        ├── ReceivedPathNode               — the participant replica alone
        ├── CaseOpenToExternalWrites       — post-close boundary (CM-23-013)
        ├── sender guard                   — only the CASE_MANAGER (PCR-03-001)
        └── IntakeReceivedActivityNode     — record what arrived (CLP-10-017)

    The answer is the recommender's to receive, and the recommender is a
    participant of the case, so the participant-replica path is the only one
    this type handles (HP-01-038).  The declaration is what refuses the
    case's own CASE_MANAGER, which ledgered the answer when it sent it and
    never receives it: the path stage names it the CASE_MANAGER of the case
    and says the type does not address that path, rather than telling the
    actual CASE_MANAGER it is not one (HP-01-039).  The stage reads the role
    in the case the ``sender_context`` names, because this tree commits
    nothing and so names no case of its own (HP-01-040).

    Args:
        name: Name for the root ``Sequence``; the handler's own tree name.
        case_id: ID of the VulnerabilityCase the answer names; ``None`` for
            an answer that names no case, which intake records and the
            tree refuses, since there is no case to check the sender
            against (CLP-10-018).
        sender_id: Actor ID of the answer's sender.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-025).

    Returns:
        Root Sequence node named *name*.
    """
    if case_id is None:
        return create_incomplete_activity_received_tree(
            name, "the answer names no case"
        )
    return create_receive_activity_tree(
        name=name,
        case_id=None,
        paths={ReceivedPath.PARTICIPANT_REPLICA},
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_id, case_id=case_id
        ),
        precondition_guards=[],
    )
