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

"""Tree factories for ownership-transfer received activities.

Provides:

- :func:`create_accept_ownership_transfer_tree` — BT for
  ``AcceptCaseOwnershipTransferReceivedUseCase``.
- :func:`create_offer_ownership_transfer_tree` — BT for
  ``OfferCaseOwnershipTransferReceivedUseCase``; wraps
  ``ForwardOfferToTransfereeNode`` in a ``create_case_manager_gated_tree``
  so only the CaseActor forwards the offer (CM-21-005, ADR-0053).
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.lifecycle import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.case.nodes.ownership_transfer import (
    AcceptCaseOwnershipTransferNode,
    ForwardOfferToTransfereeNode,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)

logger = logging.getLogger(__name__)


def create_accept_ownership_transfer_tree(
    case_id: str,
    new_owner_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``AcceptCaseOwnershipTransferReceivedUseCase``.

    Uses the standard ``create_receive_activity_tree`` factory to enforce the
    CLP-10-006 ordering: guarded-commit (CaseLedgerEntry + Announce broadcast)
    fires after ``AcceptCaseOwnershipTransferNode`` succeeds (CM-21-007).

    Args:
        case_id: URI of the case whose ownership is being transferred.
        new_owner_id: URI of the actor accepting (and becoming) the new owner.

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    tree = create_receive_activity_tree(
        name="AcceptOwnershipTransferBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=[
            AcceptCaseOwnershipTransferNode(
                case_id=case_id,
                new_owner_id=new_owner_id,
            ),
        ],
    )
    logger.debug(
        "Created AcceptOwnershipTransferBT for case='%s' new_owner='%s'",
        case_id,
        new_owner_id,
    )
    return tree


def create_offer_ownership_transfer_tree(
    case_id: str,
    transferee_id: str | None,
    original_actor_id: str | None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``OfferCaseOwnershipTransferReceivedUseCase``.

    Builds a ``create_receive_activity_tree`` whose effect section contains a
    ``create_case_manager_gated_tree`` wrapping ``ForwardOfferToTransfereeNode``
    so that only the CaseActor forwards the offer to the transferee (CM-21-005,
    ADR-0053, CLP-10-006).

    When ``transferee_id`` or ``original_actor_id`` is ``None`` the forwarding
    node is omitted: the ledger-commit gate still fires but no outbox write
    occurs.

    Args:
        case_id: URI of the case whose ownership is being offered.
        transferee_id: URI of the intended new owner; ``None`` skips forwarding.
        original_actor_id: URI of the actor who originated the offer (vendor).

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    effect_nodes: list[py_trees.behaviour.Behaviour] = []
    if transferee_id is not None and original_actor_id is not None:
        effect_nodes = [
            create_case_manager_gated_tree(
                name="ForwardOfferToTransfereeCMGated",
                case_id=case_id,
                children=[
                    ForwardOfferToTransfereeNode(
                        case_id=case_id,
                        transferee_id=transferee_id,
                        original_actor_id=original_actor_id,
                    ),
                ],
            ),
        ]
    tree = create_receive_activity_tree(
        name="OfferOwnershipTransferBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=effect_nodes,
    )
    logger.debug(
        "Created OfferOwnershipTransferBT for case='%s'"
        " transferee='%s' original_actor='%s'",
        case_id,
        transferee_id,
        original_actor_id,
    )
    return tree
