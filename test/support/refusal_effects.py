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

"""Tell a received tree's refusal effects apart from its effects.

Every received tree that commits to a case and has precondition guards
answers their refusal with the refusal notice, in a refusal stage of its own,
behind its own CASE_MANAGER gate, before the commit (CLP-02-005, CLP-10-022).
A test asking where the tree's own effects sit leaves those nodes out: they
run only when the activity is refused, never as an effect of admitting it.
"""

import py_trees

from vultron.core.behaviors.case.nodes.refusal_stage import (
    PreconditionGuardStage,
)


def refusal_effect_node_ids(tree: py_trees.behaviour.Behaviour) -> set[int]:
    """The ids of every node inside *tree*'s refusal effects."""
    return {
        id(n)
        for stage in tree.iterate()
        if isinstance(stage, PreconditionGuardStage)
        for n in stage.refusal.iterate()
    }
