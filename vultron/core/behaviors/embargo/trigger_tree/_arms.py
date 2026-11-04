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

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
    create_participant_replica_gated_tree,
)
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
        create_participant_replica_gated_tree(
            name=f"{name}{otherwise_suffix}",
            case_id=case_id,
            children=otherwise,
        ),
    ]
