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
Embargo lifecycle behavior tree compositions.

Provides factory functions for embargo-related BTs:

``remove_embargo_from_case_tree`` — handles receipt of a ``Remove(EmbargoEvent)``
activity (protocol ET message).  Sequence:

    RemoveEmbargoFromCaseBT (Sequence)
    ├─ ValidateCaseExistsNode          # case must exist and pass is_case_model
    ├─ RemoveFromProposedEmbargoesNode # idempotent proposed-list cleanup
    ├─ IsActiveEmbargoNode             # guard: is this the active embargo?
    └─ ApplyEmbargoTeardownNode        # ACTIVE/REVISE→EXITED, clear, reset PEC

Per specs/behavior-tree-integration.yaml BT-06-001.
"""

import logging

import py_trees

from vultron.core.behaviors.embargo.nodes import (
    ApplyEmbargoTeardownNode,
    IsActiveEmbargoNode,
    RemoveFromProposedEmbargoesNode,
    ValidateCaseExistsNode,
)

logger = logging.getLogger(__name__)


def remove_embargo_from_case_tree(
    case_id: str,
    embargo_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for receiver-side embargo removal (protocol ET).

    Handles receipt of a ``Remove(EmbargoEvent)`` activity.  Removes the
    embargo from ``proposed_embargoes`` (idempotent) and, if the embargo is
    the active one, applies the ACTIVE/REVISE → EXITED EM state transition,
    clears ``active_embargo``, and resets participant embargo consent states.

    BT returns SUCCESS when the active embargo is terminated.
    BT returns FAILURE when the embargo was only in ``proposed_embargoes``
    (the cleanup still runs — FAILURE is not an error condition here).

    Args:
        case_id: ID of the VulnerabilityCase to update.
        embargo_id: ID of the EmbargoEvent being removed.

    Returns:
        Root node of the ``RemoveEmbargoFromCaseBT`` Sequence.
    """
    root = py_trees.composites.Sequence(
        name="RemoveEmbargoFromCaseBT",
        memory=False,
        children=[
            ValidateCaseExistsNode(case_id=case_id),
            RemoveFromProposedEmbargoesNode(
                case_id=case_id, embargo_id=embargo_id
            ),
            IsActiveEmbargoNode(case_id=case_id, embargo_id=embargo_id),
            ApplyEmbargoTeardownNode(case_id=case_id),
        ],
    )
    logger.debug(
        "Created RemoveEmbargoFromCaseBT for case=%s embargo=%s",
        case_id,
        embargo_id,
    )
    return root
