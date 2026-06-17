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

"""
AppendParticipantStatus behavior tree composition.

Composes Step 2 of the DEMOMA-07-003 workflow as a Sequence BT with
idempotency handling via a Selector:

    AppendParticipantStatusBT (Sequence)
    ├─ LoadParticipantNode                      # Load participant from DL
    └─ IdempotencyCheckSelector (Selector)      # Skip if already appended
       ├─ SkipIfIdempotentNode                  # Already appended → SUCCESS
       └─ AppendParticipantStatusProcessNode (Sequence)
          ├─ ResolveAndPersistStatusObjectNode  # Find or create status
          ├─ ValidateRMTransitionNode           # Validate RM transition
          └─ AppendStatusAndSaveParticipantNode # Append + save

Per specs/behavior-tree-node-design.yaml BTND-07-001 (god-node decomposition).
"""

import logging

import py_trees

from vultron.core.models.protocols import PersistableModel
from vultron.core.behaviors.status.nodes import (
    AppendStatusAndSaveParticipantNode,
    LoadParticipantNode,
    ResolveAndPersistStatusObjectNode,
    SkipIfIdempotentNode,
    ValidateRMTransitionNode,
)

logger = logging.getLogger(__name__)


def append_participant_status_tree(
    status_id: str,
    participant_id: str,
    status_obj_fallback: PersistableModel | None,
) -> py_trees.behaviour.Behaviour:
    """Create the behavior tree for appending ParticipantStatus to a participant.

    Implements Step 2 of DEMOMA-07-003 as a composed subtree of five leaf nodes:
    1. Load participant from DataLayer
    2. Check idempotency (status not already appended)
    3. Resolve or persist the status object
    4. Validate RM state transition rules
    5. Append status to participant and save

    All protocol-significant behavior (participant lookup, idempotency,
    status resolution, RM validation, persistence) is represented as BT nodes
    for auditability and explainability (BTND-07-001).

    Uses a Selector to handle idempotency: if the status is already appended,
    the sequence skips the append and returns SUCCESS (idempotent).

    Args:
        status_id: The URI of the ParticipantStatus to append.
        participant_id: The URI of the CaseParticipant to update.
        status_obj_fallback: Fallback domain object to persist if status_id
            not yet in DataLayer (used for bootstrap activities).

    Returns:
        Root node of the ``AppendParticipantStatusBT`` Sequence.
    """
    append_subtree = py_trees.composites.Sequence(
        name="AppendParticipantStatusProcessNode",
        memory=False,
        children=[
            ResolveAndPersistStatusObjectNode(
                status_id=status_id,
                status_obj_fallback=status_obj_fallback,
            ),
            ValidateRMTransitionNode(participant_id=participant_id),
            AppendStatusAndSaveParticipantNode(
                status_id=status_id,
                participant_id=participant_id,
            ),
        ],
    )

    root = py_trees.composites.Sequence(
        name="AppendParticipantStatusBT",
        memory=False,
        children=[
            LoadParticipantNode(participant_id=participant_id),
            py_trees.composites.Selector(
                name="IdempotencyCheckSelector",
                memory=False,
                children=[
                    SkipIfIdempotentNode(
                        status_id=status_id,
                        participant_id=participant_id,
                    ),
                    append_subtree,
                ],
            ),
        ],
    )
    logger.debug(
        "Created AppendParticipantStatusBT for status=%s participant=%s",
        status_id,
        participant_id,
    )
    return root
