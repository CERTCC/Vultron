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

"""
Trigger-side behavior trees for the engage-case and defer-case workflows.

Each tree runs two steps in sequence:

1. **ValidateTriggerTransitionsNode** — checks that the actor has a
   participant record and that its RM state may move to the decided state,
   so an illegal decision is refused before anything is sent (BTND-10-001).
   It writes nothing.
2. **sender_side_bt** — resolves the Case Manager, constructs the outbound
   Engage/Defer activity, and queues it in the actor's outbox (PCR-08-001).

The actor does not write its own RM state.  The CASE_MANAGER records the move
when it accepts the activity and commits the status it wrote as its own
ledger entry; the actor's replica copies that status from the ledger like any
other (RSH-08-003, CLP-07-013, CM-23-016).  A local write here would give the
actor a status with its own id and time, which no entry records.
"""

from collections.abc import Callable

import py_trees

from vultron.core.behaviors.case.nodes.participant.trigger_validation import (
    ValidateTriggerTransitionsNode,
)
from vultron.core.behaviors.sender.send_tree import sender_side_bt
from vultron.core.states.rm import RM


def _decision_trigger_bt(
    name: str,
    case_id: str,
    actor_id: str,
    decided_rm: RM,
    activity_builder: Callable[[str], list[str]],
    result_out: dict | None,
) -> py_trees.behaviour.Behaviour:
    """Validate the RM move *decided_rm*, then send the decision."""
    return py_trees.composites.Sequence(
        name=name,
        memory=False,
        children=[
            ValidateTriggerTransitionsNode(
                case_id=case_id,
                actor_id=actor_id,
                rm_state=decided_rm,
                vf_state=None,
                d_state=None,
                pxa_state=None,
                result_out=result_out if result_out is not None else {},
                name=f"ValidateRMto{decided_rm.name.title()}",
                require_participant=True,
            ),
            sender_side_bt(case_id=case_id, activity_builder=activity_builder),
        ],
    )


def engage_case_trigger_bt(
    case_id: str,
    actor_id: str,
    activity_builder: Callable[[str], list[str]],
    result_out: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the engage-case (RM → ACCEPTED) workflow.

    Args:
        case_id: ID of the VulnerabilityCase to engage.
        actor_id: ID of the actor engaging the case; the subject of the
            transition check.
        activity_builder: Callable invoked by the sender subtree with the
            resolved Case Manager actor ID; should return a list of outbound
            activity IDs to queue.
        result_out: Receives the refusal under ``"error"`` when the move is
            illegal (EH-05-002).

    Returns:
        A ``py_trees.composites.Sequence`` that checks the move to ACCEPTED,
        then resolves the Case Manager, builds the Engage(Case) activity, and
        queues it in the actor's outbox.
    """
    return _decision_trigger_bt(
        "EngageCaseTriggerBT",
        case_id,
        actor_id,
        RM.ACCEPTED,
        activity_builder,
        result_out,
    )


def defer_case_trigger_bt(
    case_id: str,
    actor_id: str,
    activity_builder: Callable[[str], list[str]],
    result_out: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the defer-case (RM → DEFERRED) workflow.

    Args:
        case_id: ID of the VulnerabilityCase to defer.
        actor_id: ID of the actor deferring the case; the subject of the
            transition check.
        activity_builder: Callable invoked by the sender subtree with the
            resolved Case Manager actor ID; should return a list of outbound
            activity IDs to queue.
        result_out: Receives the refusal under ``"error"`` when the move is
            illegal (EH-05-002).

    Returns:
        A ``py_trees.composites.Sequence`` that checks the move to DEFERRED,
        then resolves the Case Manager, builds the Defer(Case) activity, and
        queues it in the actor's outbox.
    """
    return _decision_trigger_bt(
        "DeferCaseTriggerBT",
        case_id,
        actor_id,
        RM.DEFERRED,
        activity_builder,
        result_out,
    )
