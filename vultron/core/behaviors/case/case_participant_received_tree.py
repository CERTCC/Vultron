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

"""Tree factories for received Add/Remove CaseParticipant activities.

Each factory composes the corresponding leaf node through
:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
so intake archives the received activity first (CLP-10-017) and a refused
delivery still leaves its record (CLP-10-018).  The tree carries no
``case_id`` for the commit stage: these activities are not ledgered here.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.case_participant_received import (
    AddCaseParticipantToCaseReceivedNode,
    RemoveCaseParticipantFromCaseReceivedNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)

logger = logging.getLogger(__name__)


def create_add_case_participant_received_tree(
    participant_id: str,
    case_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``AddCaseParticipantToCaseReceivedUseCase``.

    Args:
        participant_id: URI of the participant to add.
        case_id: URI of the case to add the participant to.

    Returns:
        The root ``Sequence``, ready for ``BTBridge.execute_with_setup()``.
    """
    root = create_receive_activity_tree(
        name="AddCaseParticipantReceivedBT",
        case_id=None,
        precondition_guards=[],
        effect_nodes=[
            AddCaseParticipantToCaseReceivedNode(
                participant_id=participant_id,
                case_id=case_id,
            )
        ],
    )
    logger.debug(
        "Created AddCaseParticipantReceivedBT for participant='%s' case='%s'",
        participant_id,
        case_id,
    )
    return root


def create_remove_case_participant_received_tree(
    participant_id: str,
    case_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``RemoveCaseParticipantFromCaseReceivedUseCase``.

    Args:
        participant_id: URI of the participant to remove.
        case_id: URI of the case to remove the participant from.

    Returns:
        The root ``Sequence``, ready for ``BTBridge.execute_with_setup()``.
    """
    root = create_receive_activity_tree(
        name="RemoveCaseParticipantReceivedBT",
        case_id=None,
        precondition_guards=[],
        effect_nodes=[
            RemoveCaseParticipantFromCaseReceivedNode(
                participant_id=participant_id,
                case_id=case_id,
            )
        ],
    )
    logger.debug(
        "Created RemoveCaseParticipantReceivedBT"
        " for participant='%s' case='%s'",
        participant_id,
        case_id,
    )
    return root
