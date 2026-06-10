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
Trigger-side behavior tree for the add-participant-status workflow.

The tree runs two steps in sequence:

1. **CreateParticipantStatusNode** — creates the ParticipantStatus snapshot
   record and appends it to the participant's history.  The resulting
   ``status_id`` and ``participant_id`` are written to a shared
   ``result_out`` dict so the activity-builder closure can reference them.

2. **sender_side_bt** — resolves the Case Manager actor ID, calls the
   ``activity_builder`` closure with that ID, and queues the resulting
   outbound activity in the actor's outbox (PCR-08-001).

This satisfies BT-15-001: the ParticipantStatus write (protocol-significant
behavior) lives inside the BT, not directly in ``execute()``.
"""

from typing import Callable

import py_trees

from vultron.core.behaviors.case.nodes.participant import (
    CreateParticipantStatusNode,
)
from vultron.core.behaviors.sender.send_tree import sender_side_bt
from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.core.states.rm import RM


def add_participant_status_trigger_bt(
    case_id: str,
    actor_id: str,
    rm_state: "RM | None",
    vfd_state: "CS_vfd | None",
    pxa_state: "CS_pxa | None",
    result_out: dict,
    activity_builder: Callable[[str], list[str]],
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the add-participant-status workflow.

    Args:
        case_id: ID of the VulnerabilityCase.
        actor_id: ID of the actor self-reporting their status.
        rm_state: RM state override from the trigger request
            (``None`` → use the actor's current RM state).
        vfd_state: CS_vfd state override from the trigger request
            (``None`` → use the actor's current VFD state).
        pxa_state: CS_pxa value for an optional CaseStatus snapshot
            (``None`` → no CaseStatus attached).
        result_out: Mutable dict populated by
            :class:`CreateParticipantStatusNode` with ``'status_id'`` and
            ``'participant_id'``; read by the ``activity_builder`` closure
            in ``SvcAddParticipantStatusUseCase``.
        activity_builder: ``(case_manager_id: str) -> list[str]`` —
            called by ``sender_side_bt`` after resolving the Case Manager;
            must create the ``Add(ParticipantStatus)`` activity and return
            its ID in a list.

    Returns:
        A ``py_trees.composites.Sequence`` that:

        - Creates the ParticipantStatus snapshot (BT-15-001).
        - Resolves the Case Manager, builds the activity, and queues it.
    """
    return py_trees.composites.Sequence(
        name="AddParticipantStatusTriggerBT",
        memory=False,
        children=[
            CreateParticipantStatusNode(
                case_id=case_id,
                actor_id=actor_id,
                rm_state=rm_state,
                vfd_state=vfd_state,
                pxa_state=pxa_state,
                result_out=result_out,
            ),
            sender_side_bt(case_id=case_id, activity_builder=activity_builder),
        ],
    )
