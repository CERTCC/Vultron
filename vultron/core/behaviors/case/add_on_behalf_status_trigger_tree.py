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
#  Carnegie Mellon®, CERTⓇ and CERT Coordination CenterⓇ are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Trigger-side BT for the on-behalf v→V / d→D assertion workflow.

The asserting actor (Case Manager or Case Owner) records vendor-awareness
or deployer-fix-deployment on behalf of a notified-but-not-yet-joined actor.
The tree runs four steps in sequence:

1. **CheckOnBehalfAuthorizedNode** — verify the asserting actor holds
   CASE_MANAGER or CASE_OWNER (ADR-0084, PRM-06-003/004).
2. **EnsureOnBehalfParticipantExistsNode** — create a minimal
   ``CaseParticipant`` for the target if absent (ADR-0084).
3. **CreateParticipantStatusNode** — write the ParticipantStatus snapshot
   for the target actor (BT-15-001: protocol-significant write inside BT).
4. **sender_side_bt** — resolve the Case Manager, build the outbound
   ``Add(ParticipantStatus)`` activity, and queue it.
"""

from typing import Callable

import py_trees

from vultron.core.behaviors.case.nodes.participant import (
    CreateParticipantStatusNode,
)
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckOnBehalfAuthorizedNode,
    EnsureOnBehalfParticipantExistsNode,
)
from vultron.core.behaviors.sender.send_tree import sender_side_bt
from vultron.core.states.cs import CS_d, CS_vf
from vultron.enums.roles import CVDRole


def add_on_behalf_status_trigger_bt(
    case_id: str,
    asserting_actor_id: str,
    target_actor_id: str,
    required_roles: list[CVDRole],
    vf_state: "CS_vf | None",
    d_state: "CS_d | None",
    result_out: dict,
    activity_builder: Callable[[str], list[str]],
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the on-behalf status assertion workflow.

    Args:
        case_id: ID of the VulnerabilityCase.
        asserting_actor_id: Actor making the assertion (must hold CASE_MANAGER
            or CASE_OWNER).
        target_actor_id: Actor whose awareness/deployment is being recorded.
        required_roles: Roles to assign when creating a new participant;
            ``[CVDRole.VENDOR]`` for v→V, ``[CVDRole.DEPLOYER]`` for d→D,
            ``[CVDRole.VENDOR, CVDRole.DEPLOYER]`` when both are requested.
        vf_state: ``CS_vf.Vf`` for v→V, or ``None``.
        d_state: ``CS_d.D`` for d→D, or ``None``.
        result_out: Mutable dict populated by ``CreateParticipantStatusNode``
            with ``'status_id'`` and ``'participant_id'``.
        activity_builder: ``(case_manager_id: str) -> list[str]`` — called by
            ``sender_side_bt`` after resolving the Case Manager.

    Returns:
        A ``py_trees.composites.Sequence`` that gates, creates, and emits.
    """
    return py_trees.composites.Sequence(
        name="AddOnBehalfStatusTriggerBT",
        memory=False,
        children=[
            CheckOnBehalfAuthorizedNode(
                case_id=case_id,
                asserting_actor_id=asserting_actor_id,
            ),
            EnsureOnBehalfParticipantExistsNode(
                case_id=case_id,
                target_actor_id=target_actor_id,
                required_roles=required_roles,
            ),
            CreateParticipantStatusNode(
                case_id=case_id,
                actor_id=target_actor_id,
                rm_state=None,
                vf_state=vf_state,
                d_state=d_state,
                pxa_state=None,
                result_out=result_out,
            ),
            sender_side_bt(case_id=case_id, activity_builder=activity_builder),
        ],
    )
