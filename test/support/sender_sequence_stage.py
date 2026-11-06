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

"""Finding the nodes of a received tree's sender-sequence stage.

The CASE_MANAGER judges a sender's numbered activities in order in a stage of
its own, behind its own CASE_MANAGER gate, after the door and sender guards
and before the guards and commit (SYNC-21-008, SYNC-21-023).  Its writes are
the CASE_MANAGER's own bookkeeping and the refusal notice for a number, never
an effect of admitting the act, so a test asking where the tree's own effects
sit leaves those nodes out.
"""

import py_trees

from vultron.core.behaviors.sync.nodes.sender_sequence import (
    SequenceOrderStage,
)


def sender_sequence_node_ids(tree: py_trees.behaviour.Behaviour) -> set[int]:
    """The ids of every node inside *tree*'s sender-sequence stages."""
    return {
        id(n)
        for stage in tree.iterate()
        if isinstance(stage, SequenceOrderStage)
        for n in stage.iterate()
    }
