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
    ├─ ValidateCaseExistsNode          # case must exist as VulnerabilityCase
    ├─ GuardedCommitCaseLedgerEntryBT  # record receipt before effects (CLP-10-006)
    ├─ RemoveFromProposedEmbargoesNode # idempotent proposed-list cleanup
    └─ TeardownIfActive (Selector)     # run teardown if active; skip silently
       ├─ ActiveTeardown (Sequence)
       │  ├─ IsActiveEmbargoNode       # guard: is this the active embargo?
       │  └─ ApplyEmbargoTeardownNode  # ACTIVE/REVISE→EXITED, clear, reset PEC
       └─ Success                      # embargo was only in proposed — not an error

Per specs/behavior-tree-integration.yaml BT-06-001.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.nodes import (
    ApplyEmbargoTeardownNode,
    CreateAndStoreInviteNode,
    IsActiveEmbargoNode,
    OptionalLookupParticipantNode,
    RecordParticipantAcceptanceNode,
    RemoveFromProposedEmbargoesNode,
    RemoveStaleAcceptanceNode,
    SetEmbargoActiveNode,
    UpdateParticipantEmbargoPecNode,
    ValidateCaseExistsNode,
)
from vultron.core.states.participant_embargo_consent import PEC_Trigger

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
    Always commits a canonical ledger entry when the executing actor holds
    the ``CASE_MANAGER`` role (via the guarded commit subtree).

    The inner ``TeardownIfActive`` Selector absorbs the FAILURE that occurs
    when the embargo was only in ``proposed_embargoes`` (not the active
    embargo), so the outer Sequence always reaches the guarded commit step.

    BT returns SUCCESS when the outer Sequence completes (including when the
    embargo was only proposed and no teardown was needed).
    BT returns FAILURE only when the case is not found.

    Args:
        case_id: ID of the VulnerabilityCase to update.
        embargo_id: ID of the EmbargoEvent being removed.

    Returns:
        Root node of the ``RemoveEmbargoFromCaseBT`` Sequence.
    """
    teardown_if_active = py_trees.composites.Selector(
        name="TeardownIfActive",
        memory=False,
        children=[
            py_trees.composites.Sequence(
                name="ActiveTeardown",
                memory=False,
                children=[
                    IsActiveEmbargoNode(
                        case_id=case_id, embargo_id=embargo_id
                    ),
                    ApplyEmbargoTeardownNode(case_id=case_id),
                ],
            ),
            py_trees.behaviours.Success(name="EmbargoWasNotActive"),
        ],
    )
    root = create_receive_activity_tree(
        name="RemoveEmbargoFromCaseBT",
        case_id=case_id,
        precondition_guards=[ValidateCaseExistsNode(case_id=case_id)],
        effect_nodes=[
            RemoveFromProposedEmbargoesNode(
                case_id=case_id, embargo_id=embargo_id
            ),
            teardown_if_active,
        ],
    )
    logger.info(
        "Created RemoveEmbargoFromCaseBT for case=%s embargo=%s",
        case_id,
        embargo_id,
    )
    return root


def add_embargo_to_case_tree(
    case_id: str,
    embargo_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for receiver-side embargo activation (protocol EA).

    Handles receipt of an ``Add(EmbargoEvent)`` activity.  Sets the embargo
    as active on the case, transitions EM → ACTIVE, and commits a canonical
    ledger entry.

    BT returns SUCCESS when the embargo is activated.
    Always commits the ledger entry regardless of BT result.

    Args:
        case_id: ID of the VulnerabilityCase to update.
        embargo_id: ID of the EmbargoEvent being activated.

    Returns:
        Root node of the ``AddEmbargoToCaseBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="AddEmbargoToCaseBT",
        case_id=case_id,
        precondition_guards=[ValidateCaseExistsNode(case_id=case_id)],
        effect_nodes=[
            SetEmbargoActiveNode(case_id=case_id, embargo_id=embargo_id),
        ],
    )
    logger.info(
        "Created AddEmbargoToCaseBT for case=%s embargo=%s",
        case_id,
        embargo_id,
    )
    return root


def invite_to_embargo_on_case_tree(
    case_id: str,
    invitee_id: str,
    invite_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for receiving embargo invitation (protocol EI).

    Handles receipt of an ``Invite(InviteToEmbargoOnCase)`` activity.
    Stores the invite activity idempotently (always succeeds), then optionally
    looks up the invitee's participant record and advances their PEC state to
    INVITED (skips silently if case/participant not found). Finally, commits
    a canonical ledger entry.

    BT always returns SUCCESS (invite storage is idempotent).
    Always commits the ledger entry regardless of BT result.

    Args:
        case_id: ID of the VulnerabilityCase.
        invitee_id: Actor ID of the invitee.
        invite_id: ID of the InviteToEmbargoOnCase activity.

    Returns:
        Root node of the ``InviteToEmbargoOnCaseBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="InviteToEmbargoOnCaseBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=[
            CreateAndStoreInviteNode(),
            OptionalLookupParticipantNode(
                case_id=case_id, target_actor_id=invitee_id
            ),
            UpdateParticipantEmbargoPecNode(pec_trigger=PEC_Trigger.INVITE),
        ],
    )
    logger.info(
        "Created InviteToEmbargoOnCaseBT for case=%s invitee=%s invite=%s",
        case_id,
        invitee_id,
        invite_id,
    )
    return root


def accept_invite_to_embargo_tree(
    case_id: str,
    embargo_id: str,
    accepting_actor_id: str,
    invite_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for accepting embargo invitation (protocol EA).

    Handles receipt of an ``Accept(InviteToEmbargoOnCase)`` activity.
    Records the acceptance via EmbargoLifecycle and commits a canonical
    ledger entry.

    BT returns SUCCESS when acceptance is recorded.
    Always commits the ledger entry regardless of BT result.

    Args:
        case_id: ID of the VulnerabilityCase.
        embargo_id: ID of the EmbargoEvent being accepted.
        accepting_actor_id: Actor ID of the participant accepting.
        invite_id: ID of the InviteToEmbargoOnCase activity.

    Returns:
        Root node of the ``AcceptInviteToEmbargoBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="AcceptInviteToEmbargoBT",
        case_id=case_id,
        precondition_guards=[ValidateCaseExistsNode(case_id=case_id)],
        effect_nodes=[
            RecordParticipantAcceptanceNode(
                case_id=case_id,
                embargo_id=embargo_id,
                accepting_actor_id=accepting_actor_id,
            ),
        ],
    )
    logger.info(
        "Created AcceptInviteToEmbargoBT for case=%s embargo=%s"
        " accepting_actor=%s",
        case_id,
        embargo_id,
        accepting_actor_id,
    )
    return root


def reject_invite_to_embargo_tree(
    case_id: str,
    rejecting_actor_id: str,
    invite_id: str,
    embargo_id: str | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for rejecting embargo invitation (protocol EA).

    Handles receipt of a ``Reject(InviteToEmbargoOnCase)`` activity.
    Optionally looks up the rejecting participant (skips silently if
    case/participant not found), removes any stale embargo acceptance
    (pocket-veto), advances their PEC state to DECLINED, and commits
    a canonical ledger entry.

    BT always returns SUCCESS (best-effort operations).
    Always commits the ledger entry regardless of BT result.

    Args:
        case_id: ID of the VulnerabilityCase.
        rejecting_actor_id: Actor ID of the participant rejecting.
        invite_id: ID of the InviteToEmbargoOnCase activity.
        embargo_id: ID of the EmbargoEvent (optional, for pocket-veto).

    Returns:
        Root node of the ``RejectInviteToEmbargoBT`` Sequence.
    """
    effect_nodes: list[py_trees.behaviour.Behaviour] = [
        OptionalLookupParticipantNode(case_id=case_id),
        UpdateParticipantEmbargoPecNode(pec_trigger=PEC_Trigger.DECLINE),
    ]
    if embargo_id is not None:
        # Only attempt pocket-veto removal when we know which embargo to check.
        effect_nodes.insert(
            1, RemoveStaleAcceptanceNode(embargo_id=embargo_id)
        )
    root = create_receive_activity_tree(
        name="RejectInviteToEmbargoBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=effect_nodes,
    )
    logger.info(
        "Created RejectInviteToEmbargoBT for case=%s rejecting_actor=%s"
        " invite=%s",
        case_id,
        rejecting_actor_id,
        invite_id,
    )
    return root
