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

"""The received tree's type, its stage list and the guarded commit stage.

Split out of ``receive_activity_tree.py`` (CS-18-001), which re-exports
every name here.
"""

from collections.abc import Sequence

import py_trees

from vultron.core.behaviors.act_transaction import (
    ActTransaction,
    OneActExemption,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    CommitCaseLedgerEntryNode,
)
from vultron.core.behaviors.case.nodes.refusal_notice import (
    RefusalNoticeExemption,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)


def create_guarded_commit_case_ledger_entry_tree(
    case_id: str | None = None,
    case_may_be_absent: bool = False,
) -> py_trees.composites.Selector:
    """Create a guarded commit subtree for canonical case-ledger entries.

    The commit runs only when the executing actor holds ``CVDRole.CASE_MANAGER``
    for the case; see :func:`create_case_manager_gated_tree` for the gate's
    failure-mode semantics.

    Called internally by :func:`create_receive_activity_tree`.  Direct callers
    in tree-factory modules are a CLP-10-006 ordering violation; use
    ``create_receive_activity_tree`` instead.

    ``case_may_be_absent`` is passed to the gate; see
    :func:`create_receive_activity_tree`.
    """
    return create_case_manager_gated_tree(
        name="GuardedCommitCaseLedgerEntryBT",
        case_id=case_id,
        children=[CommitCaseLedgerEntryNode(case_id=case_id)],
        case_may_be_absent=case_may_be_absent,
    )


class ReceivedActivityTree(py_trees.composites.Sequence):
    """The one tree a received activity runs (CLP-10-005, ADR-0135).

    A plain ``Sequence`` that also remembers which of its children are the
    door guards (intake, the post-close guard, the addressee check and the
    sender guard, CLP-10-010), so a handler can ask whether the delivery got
    past them without knowing which guard the tree runs first, and which
    exemptions, if any, it was built with in place of the refusal notice
    (CLP-02-005) and of one act (CLP-07-015).
    """

    def __init__(
        self,
        name: str,
        children: list[py_trees.behaviour.Behaviour],
        door_guards: Sequence[py_trees.behaviour.Behaviour],
        refusal_notice_exemption: RefusalNoticeExemption | None = None,
        one_act_exemption: OneActExemption | None = None,
    ) -> None:
        super().__init__(name=name, memory=False, children=children)
        self.door_guards: tuple[py_trees.behaviour.Behaviour, ...] = tuple(
            door_guards
        )
        self.refusal_notice_exemption: RefusalNoticeExemption | None = (
            refusal_notice_exemption
        )
        self.one_act_exemption: OneActExemption | None = one_act_exemption

    @property
    def door_guards_admitted(self) -> bool:
        """True once every door guard ran and succeeded on the last tick."""
        return all(
            guard.status == py_trees.common.Status.SUCCESS
            for guard in self.door_guards
        )


def received_stages(
    tree: py_trees.behaviour.Behaviour,
) -> list[py_trees.behaviour.Behaviour]:
    """The stages *tree* runs, in order, with an act block opened in place.

    A tree that commits to a case holds its guarded commit and effects in
    one :class:`~vultron.core.behaviors.act_transaction.ActTransaction`
    child; its children stand in for it here, so a reader of the stage order
    (the commit-ordering and refusal-notice ratchets) sees the same stages
    with or without the block.
    """
    stages: list[py_trees.behaviour.Behaviour] = []
    for child in tree.children:
        if isinstance(child, ActTransaction):
            stages.extend(child.children)
        else:
            stages.append(child)
    return stages
