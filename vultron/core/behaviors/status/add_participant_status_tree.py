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
AddParticipantStatus behavior tree composition.

Composes the four-step DEMOMA-07-003 workflow as a Sequence BT
(step 3 raw peer re-broadcast removed per DEMOMA-07-005):

    AddParticipantStatusBT (Sequence)
    ├─ VerifySenderIsParticipantNode      # Step 1: sender must be known participant
    ├─ AppendParticipantStatusNode        # Step 2: append status to participant record
    ├─ PublicDisclosureBranchNode         # Step 4: embargo teardown on CS.P + CASE_OWNER
    ├─ AutoCloseIfCaseManager (Selector)  # Step 5: auto-close only when CASE_MANAGER
    │   ├─ Sequence
    │   │   ├─ CheckIsCaseManagerNode
    │   │   └─ AutoCloseBranchNode
    │   └─ Success (skip if not CASE_MANAGER)
    └─ GuardedCommitOrSkip (Selector, only if case_id)  # ADR-0022 / CLP-10-005
        ├─ Sequence
        │   ├─ CheckIsCaseManagerNode
        │   └─ CommitCaseLedgerEntryNode
        └─ Success("CommitSkippedNotCaseManager")

Per specs/multi-actor-demo.yaml DEMOMA-07-003 and DEMOMA-07-005.
"""

import logging

import py_trees

from vultron.core.models.events.status import (
    AddParticipantStatusToParticipantReceivedEvent,
)
from vultron.core.behaviors.case.nodes.conditions import CheckIsCaseManagerNode
from vultron.core.behaviors.case.nodes.lifecycle import (
    create_guarded_commit_case_ledger_entry_tree,
)
from vultron.core.behaviors.status.append_participant_status_tree import (
    append_participant_status_tree,
)
from vultron.core.behaviors.status.nodes import (
    AutoCloseBranchNode,
    PublicDisclosureBranchNode,
    VerifySenderIsParticipantNode,
)

logger = logging.getLogger(__name__)


def add_participant_status_tree(
    request: AddParticipantStatusToParticipantReceivedEvent,
    case_id: str | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the behavior tree for the AddParticipantStatus workflow.

    Handles receipt of an ``Add(ParticipantStatus, CaseParticipant)``
    activity.  Implements the four remaining steps of DEMOMA-07-003 as BT
    nodes in a Sequence (step 3 raw re-broadcast removed per DEMOMA-07-005).

    When ``case_id`` is provided, a guarded-commit subtree
    (``create_guarded_commit_case_ledger_entry_tree``) is appended as the
    final child.  Running the tree with ``actor_id=receiving_actor_id``
    (ADR-0022 single-BT shape) means ``CheckIsCaseManagerNode`` in that
    subtree correctly fires only when the receiving actor holds
    ``CVDRole.CASE_MANAGER``.

    The *case_id* for the existing children is derived from the inline
    ``request.status.context`` field.  If it is not available in the inline
    object, the ``VerifySenderIsParticipantNode`` will perform a DataLayer
    lookup.

    ``PublicDisclosureBranchNode`` uses the ``trigger_activity_factory`` that
    the caller places on the py_trees blackboard via
    ``BTBridge(trigger_activity=...)``.

    Args:
        request: The parsed inbound domain event.
        case_id: ID of the VulnerabilityCase.  When provided, a guarded-commit
            subtree is appended so the receiving CaseActor writes a canonical
            ledger entry (CLP-10-005).  Pass ``None`` to skip the commit.

    Returns:
        Root node of the ``AddParticipantStatusBT`` Sequence.
    """
    status_id = request.status_id or ""
    participant_id = request.participant_id or ""
    actor_id = request.actor_id
    status_obj = request.status

    # Derive case_id from the inline status object when not supplied explicitly.
    # VerifySenderIsParticipantNode falls back to a DataLayer lookup when None.
    tree_case_id: str | None = case_id
    if tree_case_id is None and status_obj is not None:
        context_field = getattr(status_obj, "context", None)
        if context_field:
            tree_case_id = str(context_field)

    children: list[py_trees.behaviour.Behaviour] = [
        VerifySenderIsParticipantNode(
            status_id=status_id,
            sender_actor_id=actor_id,
            case_id=tree_case_id,
        ),
        append_participant_status_tree(
            status_id=status_id,
            participant_id=participant_id,
            status_obj_fallback=status_obj,
        ),
        PublicDisclosureBranchNode(
            status_obj=status_obj,
            sender_actor_id=actor_id,
            case_id=tree_case_id,
        ),
        py_trees.composites.Selector(
            name="AutoCloseIfCaseManager",
            memory=False,
            children=[
                py_trees.composites.Sequence(
                    name="CaseManagerAutoClose",
                    memory=False,
                    children=[
                        CheckIsCaseManagerNode(case_id=tree_case_id),
                        AutoCloseBranchNode(case_id=tree_case_id),
                    ],
                ),
                py_trees.behaviours.Success(
                    name="AutoCloseSkippedNotCaseManager"
                ),
            ],
        ),
    ]

    if case_id is not None:
        children.append(
            create_guarded_commit_case_ledger_entry_tree(case_id=case_id)
        )

    root = py_trees.composites.Sequence(
        name="AddParticipantStatusBT",
        memory=False,
        children=children,
    )
    logger.debug(
        "Created AddParticipantStatusBT for status=%s participant=%s"
        " actor=%s case=%s",
        status_id,
        participant_id,
        actor_id,
        tree_case_id,
    )
    return root
