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

"""Shared tree for received handlers that only store what arrived (#3871).

Every store-only received handler builds this one tree and runs it once
(CLP-10-005): intake, then at most one effect node that stores the object the
message introduced.  There are no guards, no commit, and no other effects.

Why no commit (``case_id=None``): a ``Create(X)`` message *introduces* an
object; the assertion about the case is the ``Add`` that follows, which is
already ledgered.  Ledgering the Create as well would record the same fact
twice.  The handlers that write nothing at all (a rejected role offer, an
embargo announcement, a processing-fault NACK) still run the tree, so the
activity they received is archived (CLP-10-017, CLP-10-018).
"""

import py_trees

from vultron.core.behaviors.case.nodes.store_received_object import (
    StoreReceivedObjectNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)


def create_store_only_received_tree(
    name: str,
    store_node: StoreReceivedObjectNode | None = None,
) -> py_trees.composites.Sequence:
    """Build the intake-only tree, with an optional store-the-object effect.

    Args:
        name: Name for the root ``Sequence``.
        store_node: Stores the object a ``Create(X)`` introduced; ``None``
            for a handler whose activity carries nothing to store.
    """
    return create_receive_activity_tree(
        name=name,
        case_id=None,
        precondition_guards=[],
        replica_effects=[] if store_node is None else [store_node],
    )
