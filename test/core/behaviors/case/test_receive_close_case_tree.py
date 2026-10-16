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
"""Structure of the owner-Leave ``case_fully_closed`` commit (#4113, #3743).

``CommitCaseFullyClosedBT`` builds the CASE_MANAGER's own
``Update(VulnerabilityCase)`` and commits its sealed blob, so it carries its
own port guard: without a sync port it must refuse before the activity is
built or the entry persisted, not after.
"""

from __future__ import annotations

import py_trees

from vultron.core.behaviors.case.nodes.leave import (
    CommitCaseFullyClosedNode,
)
from vultron.core.behaviors.case.receive_close_case_tree import (
    create_close_case_received_tree,
)
from vultron.core.behaviors.sync.nodes import RequireSyncPortNode
from vultron.core.use_cases.received.case.lifecycle import (
    CloseCaseReceivedUseCase,
)

CASE_ID = "https://example.org/cases/c-close-tree"
OWNER_ID = "https://example.org/actors/owner-close-tree"


def _find(
    root: py_trees.behaviour.Behaviour, name: str
) -> py_trees.behaviour.Behaviour:
    for node in root.iterate():
        if node.name == name:
            return node
    raise AssertionError(f"no node named {name!r} in the tree")


def test_case_fully_closed_commit_guards_the_sync_port_before_persisting():
    tree = create_close_case_received_tree(
        case_id=CASE_ID,
        activity_id="https://example.org/activities/leave-1",
        sender_actor_id=OWNER_ID,
        receiving_actor_id="https://example.org/actors/case-actor",
        sender_rule=CloseCaseReceivedUseCase.sender_entitlement,
    )

    commit = _find(tree, "CommitCaseFullyClosedBT")
    children = list(commit.children)

    assert isinstance(children[0], RequireSyncPortNode)
    assert [type(child) for child in children[1:]] == [
        CommitCaseFullyClosedNode
    ]
