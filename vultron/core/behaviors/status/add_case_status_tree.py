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
AddCaseStatus behavior tree composition.

Seam 2 of the two-seam authorization model (ADR-0046, RSH-02-001 to
RSH-03-003): after the canonical CaseStatus write, a ``SideEffectsGuard``
(Selector/Fallback) gates side-effect execution, and
``ThreatTerminationBranchNode`` fires embargo teardown when the CaseStatus
signals a threat (P=True OR X=True OR A=True).

    AddCaseStatusToCaseBT (Sequence)
    ├─ CheckCaseStatusIdempotencyNode   # AC-1: status not already present
    ├─ ValidateCaseStatusTransitionNode # AC-2: EM/PXA transitions are valid
    ├─ AppendCaseStatusToCaseNode       # AC-1: append status and persist
    ├─ SideEffectsGuard (Selector)      # Seam 2 gate (RSH-02-001)
    │   └─ SideEffectsApproved         # call-out; default AlwaysSucceed
    └─ ThreatTerminationBranchNode      # Embargo teardown (RSH-03-001)

Per issue #758 (BT-SM Integration: AddCaseStatusToCaseReceivedUseCase),
RSH-02-001 to RSH-03-003, ADR-0046.
"""

import logging

import py_trees

from vultron.core.behaviors.call_out.bundles.status_authorization import (
    STATUS_AUTHORIZATION_DETERMINISTIC,
    StatusAuthorizationCallOutBundle,
)
from vultron.core.models.events.status import AddCaseStatusToCaseReceivedEvent
from vultron.core.behaviors.status.nodes import (
    AppendCaseStatusToCaseNode,
    CheckCaseStatusIdempotencyNode,
    ValidateCaseStatusTransitionNode,
)
from vultron.core.behaviors.status.nodes.threat_termination import (
    ThreatTerminationBranchNode,
)

logger = logging.getLogger(__name__)


def add_case_status_tree(
    request: AddCaseStatusToCaseReceivedEvent,
    call_out: StatusAuthorizationCallOutBundle = STATUS_AUTHORIZATION_DETERMINISTIC,
) -> py_trees.behaviour.Behaviour:
    """Create the behavior tree for the AddCaseStatusToCase workflow.

    Handles receipt of an ``Add(CaseStatus, VulnerabilityCase)`` activity.
    Implements five nodes in a Sequence:

    1. Idempotency check — fail fast if the status is already present.
    2. Transition validation — reject invalid EM or PXA state transitions.
    3. Append and persist — write the new CaseStatus to the case record.
    4. ``SideEffectsGuard`` (Selector) — Seam 2 call-out gate (RSH-02-001).
       Default is ``AlwaysSucceed``; production adapters may inject a guard
       that blocks side-effects for certain actors or scenarios.
    5. ``ThreatTerminationBranchNode`` — fires embargo teardown when the
       CaseStatus has at least one of P=True, X=True, or A=True and the case
       has an active embargo (RSH-03-001 to RSH-03-003).

    Args:
        request: The parsed inbound domain event.
        call_out: Call-out backend bundle for the ``SideEffectsGuard``.
            Defaults to :data:`STATUS_AUTHORIZATION_DETERMINISTIC` which
            approves all side-effects (historical behavior).

    Returns:
        Root node of the ``AddCaseStatusToCaseBT`` Sequence.
    """
    status_id = request.status_id or ""
    case_id = request.case_id or ""
    status_obj = request.status

    root = py_trees.composites.Sequence(
        name="AddCaseStatusToCaseBT",
        memory=False,
        children=[
            CheckCaseStatusIdempotencyNode(
                case_id=case_id,
                status_id=status_id,
            ),
            ValidateCaseStatusTransitionNode(
                case_id=case_id,
                status_id=status_id,
                status_obj_fallback=status_obj,
            ),
            AppendCaseStatusToCaseNode(
                case_id=case_id,
                status_id=status_id,
                status_obj_fallback=status_obj,
            ),
            call_out.side_effects_guard_factory("SideEffectsGuard"),
            ThreatTerminationBranchNode(
                status_obj=status_obj,
                case_id=case_id or None,
                name="ThreatTerminationBranch",
            ),
        ],
    )
    logger.debug(
        "Created AddCaseStatusToCaseBT for status=%s case=%s actor=%s"
        " (Seam 2 call-out: %s)",
        status_id,
        case_id,
        request.actor_id,
        call_out.__class__.__name__,
    )
    return root
