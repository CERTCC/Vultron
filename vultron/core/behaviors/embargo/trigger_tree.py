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

from vultron.core.behaviors.embargo.nodes import (
    AcceptEmbargoLifecycleNode,
    PersistEmbargoEventNode,
    ProposeEmbargoLifecycleNode,
    ReadEmbargoIdNode,
    RejectEmbargoLifecycleNode,
    SendTerminateEmbargoActivityNode,
    TerminateEmbargoLifecycleNode,
    ValidateEmbargoRevisionStateNode,
)
from vultron.core.behaviors.sender.nodes import (
    ConstructActivitiesNode,
    QueueToOutboxNode,
    ResolveCaseManagerNode,
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


def propose_embargo_revision_trigger_bt(
    *,
    case_id: str,
    embargo: EmbargoEvent,
    result_out: dict[str, object],
    activity_builder: Callable[[str], list[str]],
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for proposing an embargo revision.

    Differs from :func:`propose_embargo_trigger_bt` by first asserting that
    the case EM state is ACTIVE or REVISE (a revision requires an existing
    active embargo).  The lifecycle and outbound fan-out nodes are otherwise
    identical.
    """
    return py_trees.composites.Sequence(
        name="ProposeEmbargoRevisionTriggerBT",
        memory=False,
        children=[
            ValidateEmbargoRevisionStateNode(
                case_id=case_id,
                result_out=result_out,
            ),
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


def terminate_embargo_bt(
    *,
    case_id: str,
    result_out: dict[str, object],
    activity_builder: Callable[[str], list[str]] | None = None,
) -> py_trees.behaviour.Behaviour:
    """Shared BT for terminating the active embargo (BT-19-001).

    Satisfies the routing-gated state-mutation ordering:

    1. ``ReadEmbargoIdNode`` — read embargo_id from case; FAILURE if absent.
    2. ``ResolveCaseManagerNode`` — routing guard; FAILURE = no state change.
    3. ``TerminateEmbargoLifecycleNode`` — EM state mutation (after guard).
    4. Activity dispatch:
       - When ``activity_builder`` is provided: ``ConstructActivitiesNode``
         + ``QueueToOutboxNode`` (trigger path, builder closes over embargo_id).
       - When ``activity_builder`` is ``None``: ``SendTerminateEmbargoActivityNode``
         reads embargo_id and factory from the blackboard at runtime (cascade path).

    Both the trigger path (``terminate_embargo_trigger_bt``) and the
    automatic-cascade path (``PublicDisclosureBranchNode``) MUST use this
    factory so that routing prerequisites are always verified before the
    DataLayer state change is committed (BT-19-002).
    """
    if activity_builder is not None:
        dispatch_nodes: list[py_trees.behaviour.Behaviour] = [
            ConstructActivitiesNode(activity_builder=activity_builder),
            QueueToOutboxNode(),
        ]
    else:
        dispatch_nodes = [SendTerminateEmbargoActivityNode(case_id=case_id)]

    return py_trees.composites.Sequence(
        name="TerminateEmbargoBT",
        memory=True,
        children=[
            ReadEmbargoIdNode(case_id=case_id),
            ResolveCaseManagerNode(case_id=case_id),
            TerminateEmbargoLifecycleNode(
                case_id=case_id, result_out=result_out
            ),
            *dispatch_nodes,
        ],
    )


def terminate_embargo_trigger_bt(
    *,
    case_id: str,
    result_out: dict[str, object],
    activity_builder: Callable[[str], list[str]],
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for terminating the active embargo.

    Delegates to :func:`terminate_embargo_bt` (BT-19-002).
    """
    return terminate_embargo_bt(
        case_id=case_id,
        result_out=result_out,
        activity_builder=activity_builder,
    )
