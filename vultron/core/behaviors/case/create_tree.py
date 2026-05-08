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

Per specs/behavior-tree-integration.yaml BT-06 and specs/case-management.yaml
CM-02 requirements.

Structure:

    CreateCaseBT (Selector)
    ├─ CheckCaseAlreadyExists          # Early exit if case already in DataLayer
    └─ CreateCaseFlow (Sequence)
       ├─ ValidateCaseObject           # Check required fields
       ├─ SetCaseAttributedTo          # Set attributed_to to actor_id (CM-02-008)
       ├─ PersistCase                  # Save VulnerabilityCase to DataLayer
       ├─ RecordCaseCreationEvents     # Backfill offer_received + case_created events (CM-02-009)
       ├─ CreateCaseOwnerParticipant   # Add case owner as initial participant (CM-02-008)
       ├─ CreateCaseActorNode          # Create CaseActor service (CM-02-001)
       ├─ EmitCreateCaseActivity       # Generate CreateCaseActivity activity
       ├─ UpdateActorOutbox            # Append activity to actor outbox
       └─ CommitCaseLogEntryNode       # Log entry → Announce fan-out (SYNC-02-002)
"""

import logging

import py_trees

from vultron.core.models.actor_config import ActorConfig
from vultron.core.models.vultron_types import VultronCase
from vultron.core.behaviors.case.nodes import (
    CheckCaseAlreadyExists,
    CommitCaseLogEntryNode,
    CreateCaseActorNode,
    CreateCaseOwnerParticipant,
    EmitCreateCaseActivity,
    PersistCase,
    RecordCaseCreationEvents,
    SetCaseAttributedTo,
    UpdateActorOutbox,
    ValidateCaseObject,
)

logger = logging.getLogger(__name__)


def create_create_case_tree(
    case_obj: VultronCase,
    actor_id: str,
    actor_config: ActorConfig | None = None,
) -> py_trees.behaviour.Behaviour:
    """
    Create behavior tree for the create_case workflow.

    Handles receipt of CreateCaseActivity (Create(VulnerabilityCase)): persists
    the case to the DataLayer, creates the associated CaseActor, and
    emits a CreateCaseActivity activity to the actor outbox.

    The root is a Selector so that if the case already exists the tree
    succeeds immediately (idempotency per ID-04-004).

    Args:
        case_obj: Case domain object extracted from the inbound
                  Create activity payload
        actor_id: ID of the receiving actor (case owner)
        actor_config: Optional actor configuration carrying CVD-role
                      defaults.  When ``None`` the case-owner participant
                      receives only the ``CVDRole.CASE_OWNER`` role
                      (CFG-07-002, CFG-07-004).

    Returns:
        Root node of the create_case behavior tree (Selector)
    """
    case_id = case_obj.id_

    create_case_flow = py_trees.composites.Sequence(
        name="CreateCaseFlow",
        memory=False,
        children=[
            ValidateCaseObject(case_obj=case_obj),
            SetCaseAttributedTo(case_obj=case_obj),
            PersistCase(case_obj=case_obj),
            RecordCaseCreationEvents(case_obj=case_obj),
            CreateCaseOwnerParticipant(
                case_obj=case_obj, actor_config=actor_config
            ),
            CreateCaseActorNode(case_id=case_id),
            EmitCreateCaseActivity(),
            UpdateActorOutbox(),
            CommitCaseLogEntryNode(case_id=case_id),
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
