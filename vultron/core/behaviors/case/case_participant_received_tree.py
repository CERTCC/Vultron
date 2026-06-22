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

Each factory returns a minimal ``py_trees`` behaviour that wraps the
corresponding leaf node for use with ``BTBridge.execute_with_setup()``.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.case_participant_received import (
    AddCaseParticipantToCaseReceivedNode,
    RemoveCaseParticipantFromCaseReceivedNode,
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
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    root = AddCaseParticipantToCaseReceivedNode(
        participant_id=participant_id,
        case_id=case_id,
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
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    root = RemoveCaseParticipantFromCaseReceivedNode(
        participant_id=participant_id,
        case_id=case_id,
    )
    logger.debug(
        "Created RemoveCaseParticipantReceivedBT"
        " for participant='%s' case='%s'",
        participant_id,
        case_id,
    )
    return root
