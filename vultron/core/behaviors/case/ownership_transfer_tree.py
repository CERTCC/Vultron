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
  ``OfferCaseOwnershipTransferReceivedUseCase``; passes
  ``ForwardOfferToTransfereeNode`` as ``manager_effects`` so the factory's
  CASE_MANAGER gate lets only the CaseActor forward the offer (CM-21-005,
  ADR-0053, BT-17-008).
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.ownership_transfer import (
    AcceptCaseOwnershipTransferNode,
    ForwardOfferToTransfereeNode,
)
from vultron.core.behaviors.case.nodes.store_received_object import (
    StoreReceivedObjectNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
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
        replica_effects=[
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
    case_id: str | None,
    transferee_id: str | None,
    original_actor_id: str | None,
    store_offer: StoreReceivedObjectNode | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``OfferCaseOwnershipTransferReceivedUseCase``.

    Builds a ``create_receive_activity_tree`` whose ``manager_effects`` hold
    ``ForwardOfferToTransfereeNode``, so the factory's CASE_MANAGER gate
    ensures only the CaseActor forwards the offer to the transferee
    (CM-21-005, ADR-0053, CLP-10-006, BT-17-008).

    When ``transferee_id`` or ``original_actor_id`` is ``None`` the forwarding
    node is omitted: the ledger-commit gate still fires but no outbox write
    occurs.

    Args:
        case_id: URI of the case whose ownership is being offered; ``None``
            for an Offer that names no case, which is archived and kept but
            commits and forwards nothing (CLP-10-018).
        transferee_id: URI of the intended new owner; ``None`` skips forwarding.
        original_actor_id: URI of the actor who originated the offer (vendor).
        store_offer: Effect node that writes the Offer activity the accept
            trigger reads back by id (DL-06); it runs before the gated
            forward, after the guards and the commit (CLP-10-017,
            CLP-10-019).

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    replica_effects: list[py_trees.behaviour.Behaviour] = []
    if store_offer is not None:
        replica_effects.append(store_offer)
    manager_effects: list[py_trees.behaviour.Behaviour] = []
    if (
        case_id is not None
        and transferee_id is not None
        and original_actor_id is not None
    ):
        manager_effects.append(
            ForwardOfferToTransfereeNode(
                case_id=case_id,
                transferee_id=transferee_id,
                original_actor_id=original_actor_id,
            )
        )
    tree = create_receive_activity_tree(
        name="OfferOwnershipTransferBT",
        case_id=case_id,
        precondition_guards=[],
        replica_effects=replica_effects,
        manager_effects=manager_effects,
        manager_case_id=case_id if manager_effects else None,
        manager_gate_name=(
            "ForwardOfferToTransfereeCMGated" if manager_effects else None
        ),
    )
    logger.debug(
        "Created OfferOwnershipTransferBT for case='%s'"
        " transferee='%s' original_actor='%s'",
        case_id,
        transferee_id,
        original_actor_id,
    )
    return tree
