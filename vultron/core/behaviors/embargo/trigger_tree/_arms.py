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

"""The role split every trigger-side embargo tree ends with.

``_by_role`` builds the two mutually exclusive arms (the CASE_MANAGER's act
and the non-manager's ask), and ``_asserting`` adapts an activity builder to
the ask arm's one-recipient shape (PCR-08-001, SYNC-11-002).
"""

from collections.abc import Callable

import py_trees

from vultron.core.behaviors.case.nodes.conditions import CheckIsCaseManagerNode
from vultron.core.behaviors.case.nodes.path_branch import wrap_children
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.behaviors.case_status_snapshot import (
    EmitCaseStatusUpdateNode,
)
from vultron.core.behaviors.embargo.nodes import (
    EmbargoActivityBuilder,
)
from vultron.core.models.pending_assertion import (
    ASSERTED_ACTIVITY_KEY,
)


def _make_emit_node(case_id: str) -> py_trees.behaviour.Behaviour:
    return EmitCaseStatusUpdateNode(
        case_id=case_id, name="EmitCaseStatusUpdate"
    )


def _asserting(
    builder: EmbargoActivityBuilder, result_out: dict[str, object]
) -> Callable[[str], list[str]]:
    """Adapt *builder* to the sender nodes' one-recipient shape.

    The activity goes to the CASE_MANAGER alone, and its id is written to
    ``result_out[ASSERTED_ACTIVITY_KEY]`` for the pending-assertion record.
    """

    def _build(case_manager_id: str) -> list[str]:
        activity_id, _blob = builder([case_manager_id])
        result_out[ASSERTED_ACTIVITY_KEY] = activity_id
        return [activity_id]

    return _build


#: Name suffix of ``reject_proposed_embargo_bt``'s non-manager arm, which
#: asks nothing (EMB-16-002).
ABANDONMENT_LEFT_TO_CASE_MANAGER = "LeaveToCaseManager"


def _skip_at_case_manager(
    name: str,
    case_id: str,
    children: list[py_trees.behaviour.Behaviour],
) -> py_trees.composites.Selector:
    """Run *children* only when the executing actor is **not** the CASE_MANAGER.

    The complement of
    :func:`~vultron.core.behaviors.case.nodes.role_gates.create_case_manager_gated_tree`,
    kept here because the trigger side is the only caller left: a trigger runs
    on the actor's own initiative, so no received path chose it and there is no
    path stage whose answer the arm could read (ADR-0153 governs the received
    side alone).  A received tree asks for this with
    :meth:`~vultron.core.behaviors.case.nodes.path_branch.OnPaths.off_case_manager`
    instead, and the factory builds the branch (HP-01-038).

    Structure::

        <name> (Selector)
        ├── SkipIfCaseManager (CheckIsCaseManagerNode)  # SUCCESS when it is
        └── <children>                                  # only when it is not

    No ``Inverter`` is needed and no failure is masked: the first arm is a
    pure condition, so a Selector that falls through to *children* reports
    their FAILURE as its own.
    """
    return py_trees.composites.Selector(
        name=name,
        memory=False,
        children=[
            with_case_id(
                CheckIsCaseManagerNode(name="SkipIfCaseManager"), case_id
            ),
            wrap_children(name, children),
        ],
    )


def _by_role(
    name: str,
    case_id: str,
    as_case_manager: list[py_trees.behaviour.Behaviour],
    otherwise: list[py_trees.behaviour.Behaviour],
    otherwise_suffix: str = "AskCaseManager",
) -> list[py_trees.behaviour.Behaviour]:
    """The two mutually exclusive arms every embargo trigger tree ends with.

    The CASE_MANAGER arm is one act: its commit and every consequence a
    later node in the arm commits (the stub re-issue, a proposal's relay)
    run in one ``ActTransaction``, so a failure anywhere in the arm keeps
    nothing it wrote (CLP-07-015, ADR-0146).  *otherwise_suffix* names the
    non-manager arm for what it does; the default fits every arm that asks
    the CASE_MANAGER.
    """
    return [
        create_case_manager_gated_tree(
            name=f"{name}AsCaseManager",
            case_id=case_id,
            children=as_case_manager,
            as_one_act=True,
        ),
        _skip_at_case_manager(
            name=f"{name}{otherwise_suffix}",
            case_id=case_id,
            children=otherwise,
        ),
    ]
