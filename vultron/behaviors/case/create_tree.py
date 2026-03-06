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
Case creation behavior tree composition.

Composes the create_case workflow as a behavior tree with idempotency
guard, validation, persistence, CaseActor setup, and outbox update.

Per specs/behavior-tree-integration.md BT-06 and specs/case-management.md
CM-02 requirements.

Structure:

    CreateCaseBT (Selector)
    ├─ CheckCaseAlreadyExists      # Early exit if case already in DataLayer
    └─ CreateCaseFlow (Sequence)
       ├─ ValidateCaseObject       # Check required fields
       ├─ PersistCase              # Save VulnerabilityCase to DataLayer
       ├─ CreateCaseActorNode      # Create CaseActor service (CM-02-001)
       ├─ EmitCreateCaseActivity   # Generate CreateCase activity
       └─ UpdateActorOutbox        # Append activity to actor outbox
"""

import logging

import py_trees

from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.behaviors.case.nodes import (
    CheckCaseAlreadyExists,
    CreateCaseActorNode,
    EmitCreateCaseActivity,
    PersistCase,
    UpdateActorOutbox,
    ValidateCaseObject,
)

logger = logging.getLogger(__name__)


def create_create_case_tree(
    case_obj: VulnerabilityCase,
    actor_id: str,
) -> py_trees.behaviour.Behaviour:
    """
    Create behavior tree for the create_case workflow.

    Handles receipt of CreateCase (Create(VulnerabilityCase)): persists
    the case to the DataLayer, creates the associated CaseActor, and
    emits a CreateCase activity to the actor outbox.

    The root is a Selector so that if the case already exists the tree
    succeeds immediately (idempotency per ID-04-004).

    Args:
        case_obj: VulnerabilityCase object extracted from the inbound
                  Create activity payload
        actor_id: ID of the receiving actor (case owner)

    Returns:
        Root node of the create_case behavior tree (Selector)
    """
    case_id = case_obj.as_id

    create_case_flow = py_trees.composites.Sequence(
        name="CreateCaseFlow",
        memory=False,
        children=[
            ValidateCaseObject(case_obj=case_obj),
            PersistCase(case_obj=case_obj),
            CreateCaseActorNode(case_id=case_id, actor_id=actor_id),
            EmitCreateCaseActivity(),
            UpdateActorOutbox(),
        ],
    )

    root = py_trees.composites.Selector(
        name="CreateCaseBT",
        memory=False,
        children=[
            CheckCaseAlreadyExists(case_id=case_id),
            create_case_flow,
        ],
    )

    logger.debug(f"Created CreateCaseBT for case={case_id}, actor={actor_id}")
    return root
