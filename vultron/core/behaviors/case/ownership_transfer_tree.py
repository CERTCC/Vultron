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

"""Tree factory for Accept(OfferCaseOwnershipTransfer) received activities.

Wraps ``AcceptCaseOwnershipTransferNode`` for use with
``BTBridge.execute_with_setup()``.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.actor import (
    AcceptCaseOwnershipTransferNode,
)

logger = logging.getLogger(__name__)


def create_accept_ownership_transfer_tree(
    case_id: str,
    new_owner_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``AcceptCaseOwnershipTransferReceivedUseCase``.

    Args:
        case_id: URI of the case whose ownership is being transferred.
        new_owner_id: URI of the actor accepting (and becoming) the new owner.

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    root = AcceptCaseOwnershipTransferNode(
        case_id=case_id,
        new_owner_id=new_owner_id,
    )
    logger.debug(
        "Created AcceptOwnershipTransferBT for case='%s' new_owner='%s'",
        case_id,
        new_owner_id,
    )
    return root
