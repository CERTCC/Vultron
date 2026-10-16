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

"""Behavior tree for the ``leave-case`` trigger (TRIG-13, ADR-0145).

An actor closes its part in a case by sending ``Leave(VulnerabilityCase)`` to
the case's CASE_MANAGER, which decides what the Leave means (CM-23-002,
CM-23-003).  Before it sends, the leaving actor runs its own pre-close
integration step, the ``PreCloseAction`` Actuator call-out (TRIG-13-002).  A
Case Owner whose replica records an embargo in force is refused first, before
that step runs, because the CASE_MANAGER would decline its Leave (CM-23-011,
TRIG-13-003).
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import py_trees

from vultron.core.behaviors.call_out.bundles.close_report import (
    CLOSE_REPORT_DETERMINISTIC,
)
from vultron.core.behaviors.case.nodes.leave import (
    RefuseOwnerLeaveWhileEmbargoedNode,
)
from vultron.core.behaviors.case.owner_close_embargo_guards import (
    owner_close_blocked_by_embargo_guards,
)
from vultron.core.behaviors.sender.send_tree import sender_side_bt

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.close_report import (
        CloseReportCallOutBundle,
    )

logger = logging.getLogger(__name__)


def create_leave_case_trigger_tree(
    actor_id: str,
    case_id: str,
    activity_builder: Callable[[str], list[str]],
    result_out: dict[str, object],
    call_out: "CloseReportCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the ``leave-case`` trigger.

    Structure::

        LeaveCaseTriggerBT (Sequence)
        ├─ OwnerLeaveNotBlockedByEmbargo (Selector)
        │   ├─ NotOwnerLeaveBlockedByEmbargo (Inverter)
        │   │   └─ OwnerLeaveBlockedByEmbargoCheck (Sequence)
        │   │       ├─ CheckIsCaseOwnerForClose        # actor is CASE_OWNER
        │   │       ├─ ReadEmStateForCloseGuard
        │   │       └─ IsCloseBlockedByActiveEmbargo   # EM ACTIVE / REVISE
        │   └─ RefuseOwnerLeaveWhileEmbargoed          # FAILURE + 409 error
        ├─ PreCloseAction                              # Actuator call-out
        └─ SenderSideBT                                # resolve CM, build, queue

    The embargo check is the one the CASE_MANAGER makes on receipt
    (:func:`~vultron.core.behaviors.case.owner_close_embargo_guards
    .owner_close_blocked_by_embargo_guards`), so a participant that is not
    the owner is never blocked by it.  A check that cannot answer admits the
    Leave rather than refusing it: the CASE_MANAGER still makes the same
    check on receipt and declines an embargoed owner close (CM-23-011).

    Args:
        actor_id: The actor leaving the case.
        case_id: The case it leaves.
        activity_builder: ``(case_manager_id) -> [activity_id]``; builds and
            persists the ``Leave(VulnerabilityCase)``, as
            :func:`~vultron.core.behaviors.sender.send_tree.sender_side_bt`
            takes it.
        result_out: Mutable dict; ``result_out["error"]`` is set to a
            ``VultronInvalidStateTransitionError`` when the Case Owner is
            refused under a live embargo.
        call_out: Optional bundle supplying ``pre_close_action_factory``.
            Defaults to :data:`~vultron.core.behaviors.call_out.bundles
            .close_report.CLOSE_REPORT_DETERMINISTIC` (``AlwaysSucceed``).

    Returns:
        Root node of the ``LeaveCaseTriggerBT`` Sequence.
    """
    bundle = call_out if call_out is not None else CLOSE_REPORT_DETERMINISTIC

    embargo_guard = py_trees.composites.Selector(
        name="OwnerLeaveNotBlockedByEmbargo",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="NotOwnerLeaveBlockedByEmbargo",
                child=py_trees.composites.Sequence(
                    name="OwnerLeaveBlockedByEmbargoCheck",
                    memory=False,
                    children=owner_close_blocked_by_embargo_guards(
                        closing_actor_id=actor_id,
                        case_id=case_id,
                        result_out={},
                    ),
                ),
            ),
            RefuseOwnerLeaveWhileEmbargoedNode(
                actor_id=actor_id,
                case_id=case_id,
                result_out=result_out,
            ),
        ],
    )

    root = py_trees.composites.Sequence(
        name="LeaveCaseTriggerBT",
        memory=False,
        children=[
            embargo_guard,
            bundle.pre_close_action_factory("PreCloseAction"),
            sender_side_bt(case_id=case_id, activity_builder=activity_builder),
        ],
    )
    logger.debug(
        "Created LeaveCaseTriggerBT for actor=%s case=%s", actor_id, case_id
    )
    return root
