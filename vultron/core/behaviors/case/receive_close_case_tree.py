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

"""Received-side BT factory for the close-case workflow (ADR-0022)."""

import logging
from typing import Any

import py_trees

from vultron.core.behaviors.case.nodes.lifecycle import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.report.nodes.storage import StoreActivityNode

logger = logging.getLogger(__name__)


def create_close_case_received_tree(
    case_id: str,
    activity_id: str,
    activity_obj: Any,
) -> py_trees.composites.Sequence:
    """Single-BT received-side tree for CloseCaseReceived (ADR-0022).

    Structure::

        CloseCaseBT (Sequence)
        ├── GuardedCommitOrSkip (Selector)             # Record receipt (CLP-10-006)
        │   ├── Sequence
        │   │   ├── CheckIsCaseManagerNode
        │   │   └── CommitCaseLedgerEntryNode
        │   └── Success("CommitSkippedNotCaseManager")
        └── StoreActivityNode("Leave")                 # Persist inbound Leave activity

    Running under ``actor_id=receiving_actor_id`` means
    ``CheckIsCaseManagerNode`` naturally gates the commit to the actor that
    holds ``CVDRole.CASE_MANAGER`` — no identity comparison needed in Python.

    Args:
        case_id: ID of the VulnerabilityCase being closed.
        activity_id: ID of the inbound Leave activity to store idempotently.
        activity_obj: The wire activity object to persist.

    Returns:
        Root ``CloseCaseBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="CloseCaseBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=[
            StoreActivityNode(
                activity_id=activity_id,
                activity_obj=activity_obj,
                label="Leave",
            ),
        ],
    )
