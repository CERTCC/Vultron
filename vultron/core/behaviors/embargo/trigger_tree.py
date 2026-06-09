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

"""Trigger-side embargo BT compositions."""

from collections.abc import Callable

import py_trees

from vultron.core.behaviors.embargo.trigger_nodes import (
    AcceptEmbargoLifecycleNode,
    PersistEmbargoEventNode,
    ProposeEmbargoLifecycleNode,
    RejectEmbargoLifecycleNode,
    TerminateEmbargoLifecycleNode,
)
from vultron.core.behaviors.sender.send_tree import sender_side_bt
from vultron.core.models.embargo_event import EmbargoEvent


def propose_embargo_trigger_bt(
    *,
    case_id: str,
    embargo: EmbargoEvent,
    result_out: dict[str, object],
    activity_builder: Callable[[str], list[str]],
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for proposing or revising an embargo."""
    return py_trees.composites.Sequence(
        name="ProposeEmbargoTriggerBT",
        memory=False,
        children=[
            ProposeEmbargoLifecycleNode(
                case_id=case_id,
                embargo_id=embargo.id_,
                result_out=result_out,
            ),
            PersistEmbargoEventNode(embargo=embargo),
            sender_side_bt(case_id=case_id, activity_builder=activity_builder),
        ],
    )


def accept_embargo_trigger_bt(
    *,
    case_id: str,
    embargo_id: str,
    result_out: dict[str, object],
    activity_builder: Callable[[str], list[str]],
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for accepting an embargo invite."""
    return py_trees.composites.Sequence(
        name="AcceptEmbargoTriggerBT",
        memory=False,
        children=[
            AcceptEmbargoLifecycleNode(
                case_id=case_id,
                embargo_id=embargo_id,
                result_out=result_out,
            ),
            sender_side_bt(case_id=case_id, activity_builder=activity_builder),
        ],
    )


def reject_embargo_trigger_bt(
    *,
    case_id: str,
    embargo_id: str,
    result_out: dict[str, object],
    activity_builder: Callable[[str], list[str]],
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for rejecting an embargo invite."""
    return py_trees.composites.Sequence(
        name="RejectEmbargoTriggerBT",
        memory=False,
        children=[
            RejectEmbargoLifecycleNode(
                case_id=case_id,
                embargo_id=embargo_id,
                result_out=result_out,
            ),
            sender_side_bt(case_id=case_id, activity_builder=activity_builder),
        ],
    )


def terminate_embargo_trigger_bt(
    *,
    case_id: str,
    result_out: dict[str, object],
    activity_builder: Callable[[str], list[str]],
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for terminating the active embargo."""
    return py_trees.composites.Sequence(
        name="TerminateEmbargoTriggerBT",
        memory=False,
        children=[
            TerminateEmbargoLifecycleNode(
                case_id=case_id, result_out=result_out
            ),
            sender_side_bt(case_id=case_id, activity_builder=activity_builder),
        ],
    )
