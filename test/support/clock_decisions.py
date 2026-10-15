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

"""Tell a received tree's clock decisions apart from its effects.

Every received tree with a case and a sender guard runs the CASE_MANAGER's
case-wide clock decisions (the embargo end-time check) in a stage of its own,
behind its own CASE_MANAGER gate, before the precondition guards
(CLP-10-025, ADR-0135).  A test asking where the tree's own effects sit
leaves those nodes out: they are the CASE_MANAGER's decisions, not effects
of the received activity.
"""

import py_trees

from vultron.core.behaviors.case.nodes.clock_decision_stage import (
    ClockDecisionStage,
)


def clock_decision_node_ids(tree: py_trees.behaviour.Behaviour) -> set[int]:
    """The ids of every node inside *tree*'s clock-decision stages."""
    return {
        id(n)
        for stage in tree.iterate()
        if isinstance(stage, ClockDecisionStage)
        for n in stage.iterate()
    }
