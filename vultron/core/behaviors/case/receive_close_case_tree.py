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

"""Received-side BT factory for the close-case workflow (ADR-0022).

Implements receiver-side role semantics for Leave(VulnerabilityCase):

- **Owner Leave** (sender holds ``CVDRole.CASE_OWNER``): advances the leaving
  participant to ``RM.CLOSED``, then advances the CaseActor to ``RM.CLOSED``,
  completing the full case closure sequence on the Case Actor replica
  (CM-23-002).
- **Non-owner Leave**: advances only the leaving participant to ``RM.CLOSED``;
  the case remains open for remaining participants (CM-23-003).

The role check is performed by :class:`~vultron.core.behaviors.case.nodes
.vfd_role_guards.CheckIsCaseOwnerNode` as a tree-level condition node, per
BTND-08-001/BTND-08-002 (role checks MUST be in the tree, not in action node
``update()`` logic).

Fan-out to non-CaseActor replicas is handled by
:class:`~vultron.core.behaviors.sync.nodes.effects.ApplyCloseCaseFromLedgerNode`
in the announce tree, which mirrors the participant departure effect on every
other replica.
"""

import logging
from typing import Any

import py_trees

from vultron.core.behaviors.case.nodes.leave import (
    AdvanceCaseActorToRMClosedNode,
    AdvanceParticipantToRMClosedNode,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckIsCaseOwnerNode,
)
from vultron.core.behaviors.report.nodes.storage import StoreActivityNode

logger = logging.getLogger(__name__)


def create_close_case_received_tree(
    case_id: str,
    activity_id: str,
    activity_obj: Any,
    sender_actor_id: str | None = None,
    receiving_actor_id: str | None = None,
) -> py_trees.composites.Sequence:
    """Single-BT received-side tree for CloseCaseReceived (ADR-0022).

    When ``sender_actor_id`` is provided, the tree branches on the sender's
    ``CVDRole.CASE_OWNER`` role (CM-23-002/CM-23-003):

    - Owner Leave → advance leaving participant to ``RM.CLOSED``, then
      advance the CaseActor to ``RM.CLOSED`` (owner path, CM-23-002).
    - Non-owner Leave → advance only the leaving participant to ``RM.CLOSED``;
      case remains open (non-owner path, CM-23-003).

    When ``sender_actor_id`` is ``None`` (e.g., in legacy paths or tests that
    do not supply it), the tree falls back to the pre-#1901 behaviour:
    ``StoreActivityNode`` only, no participant state mutation.

    Structure (with role semantics)::

        CloseCaseBT (Sequence)
        ├── GuardedCommitOrSkip (Selector)             # Record receipt (CLP-10-006)
        │   ├── Sequence(SkipIfNotCaseManager)
        │   │   └── Inverter(CheckIsCaseManagerNode)
        │   └── CommitCaseLedgerEntryNode
        ├── OwnerOrNonOwnerEffects (Selector)           # Role discriminator
        │   ├── OwnerLeaveSeq (Sequence)                # Owner path
        │   │   ├── CheckIsCaseOwnerNode                # guard: sender IS CASE_OWNER
        │   │   ├── AdvanceParticipantToRMClosedNode    # step 1: owner → RM.CLOSED
        │   │   └── AdvanceCaseActorToRMClosedNode      # step 2: CaseActor → RM.CLOSED
        │   └── NonOwnerLeaveFallbackSeq (Sequence)     # Non-owner path (fallback)
        │       └── AdvanceParticipantToRMClosedNode    # departing participant → RM.CLOSED
        └── StoreActivityNode("Leave")                  # Persist inbound Leave activity

    Running under ``actor_id=receiving_actor_id`` means
    ``CheckIsCaseManagerNode`` naturally gates the commit to the actor that
    holds ``CVDRole.CASE_MANAGER`` — no identity comparison needed in Python.

    Args:
        case_id: ID of the VulnerabilityCase being closed.
        activity_id: ID of the inbound Leave activity to store idempotently.
        activity_obj: The wire activity object to persist.
        sender_actor_id: Actor URI of the Leave sender (resolved from the
            inbound Leave activity's ``actor`` field).  When provided, the tree
            applies role-discriminating RM closure effects (CM-23-002/003).
            When ``None``, only ``StoreActivityNode`` runs as a fallback.
        receiving_actor_id: Actor URI of the receiving actor.  Used as the
            ``case_actor_id`` argument of :class:`AdvanceCaseActorToRMClosedNode`
            so that the CaseActor's own RM state is advanced on owner Leave.

    Returns:
        Root ``CloseCaseBT`` Sequence node.
    """
    store_node = StoreActivityNode(
        activity_id=activity_id,
        activity_obj=activity_obj,
        label="Leave",
    )

    if sender_actor_id is None:
        return create_receive_activity_tree(
            name="CloseCaseBT",
            case_id=case_id,
            precondition_guards=[],
            effect_nodes=[store_node],
        )

    advance_leaving_participant = AdvanceParticipantToRMClosedNode(
        leaving_actor_id=sender_actor_id,
        case_id=case_id,
        name="AdvanceLeavingParticipantToRMClosed",
    )

    owner_leave_children: list[py_trees.behaviour.Behaviour] = [
        CheckIsCaseOwnerNode(
            sender_actor_id=sender_actor_id,
            case_id=case_id,
            name="CheckIsCaseOwnerForLeave",
        ),
        AdvanceParticipantToRMClosedNode(
            leaving_actor_id=sender_actor_id,
            case_id=case_id,
            name="AdvanceOwnerToRMClosed",
        ),
    ]
    if receiving_actor_id is not None:
        owner_leave_children.append(
            AdvanceCaseActorToRMClosedNode(
                case_actor_id=receiving_actor_id,
                case_id=case_id,
                name="AdvanceCaseActorToRMClosed",
            )
        )

    owner_or_non_owner_effects = py_trees.composites.Selector(
        name="OwnerOrNonOwnerEffects",
        memory=False,
        children=[
            py_trees.composites.Sequence(
                name="OwnerLeaveSeq",
                memory=False,
                children=owner_leave_children,
            ),
            py_trees.composites.Sequence(
                name="NonOwnerLeaveFallbackSeq",
                memory=False,
                children=[advance_leaving_participant],
            ),
        ],
    )

    return create_receive_activity_tree(
        name="CloseCaseBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=[
            owner_or_non_owner_effects,
            store_node,
        ],
    )
