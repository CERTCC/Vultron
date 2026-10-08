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

"""Case update behavior tree composition."""

from __future__ import annotations

import logging

import py_trees

from vultron.core.behaviors.case.nodes.update import (
    ApplyCaseUpdateNode,
    BroadcastCaseUpdateNode,
    CaptureCaseUpdateBroadcastExclusionsNode,
    CheckCaseUpdateOwnerNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.models.events.case import UpdateCaseReceivedEvent

logger = logging.getLogger(__name__)


def create_update_case_received_tree(
    case_id: str,
    actor_id: str,
    request: UpdateCaseReceivedEvent,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for UpdateCaseReceivedUseCase.

    Structure (the four CLP-10-010 stages, ADR-0111)::

        UpdateCaseBT (Sequence)
        ├── IntakeReceivedActivityNode                 # intake
        ├── CheckCaseUpdateOwnerNode                   # guard (on the *sender*)
        ├── CaptureCaseUpdateBroadcastExclusionsNode   # effects …
        ├── ApplyCaseUpdateNode
        └── GuardedBroadcastCaseUpdateBT (Selector)
            ├── SkipIfNotCaseManager (Sequence)
            │   └── Inverter(CheckIsCaseManagerNode)
            └── BroadcastCaseUpdateNode

    Composed through :func:`create_receive_activity_tree`, which supplies the
    intake node (CLP-10-017).  The commit stage is omitted (``case_id=None``)
    by decision, not by accident: an owner's ``Update(VulnerabilityCase)`` is
    deliberately not a ledgered assertion (ADR-0111, "An owner's
    ``Update(VulnerabilityCase)`` is not a ledgered assertion", #3936), so a
    guarded commit here would be refused by the canonical-entry check.  The
    CASE_MANAGER publishes the update through ``BroadcastCaseUpdateNode``
    instead (CM-06-001).

    Every actor applies the update to its own replica; only the case's
    ``CASE_MANAGER`` announces it (CM-06-001).  The gate is on the **role**
    resolved from the case — not on a comparison against a separately computed
    CaseActor id — because the authority is a role held in the case and its
    holder may be any Actor type.  This mirrors CLP-09, which already role-gates
    canonical ledger commits: appending to the log and announcing the append are
    one privilege.

    Ungated, any actor processing an ``Update(VulnerabilityCase)`` would emit an
    ``Announce`` authored as itself to every participant, which for a
    non-authoritative actor is identity spoofing.  A non-manager therefore
    *skips* the broadcast (Success) rather than failing: applying the update
    locally is correct and expected.  The broadcast is passed as
    ``manager_effects``, so the factory wraps it in
    :func:`create_case_manager_gated_tree` (BTND-07-005, BT-17-008) and a
    broadcast that fails *at* the CASE_MANAGER propagates rather than reading
    as a skip (BT-14-001).
    """
    root = create_receive_activity_tree(
        name="UpdateCaseBT",
        # No commit stage: deliberately not a ledgered assertion (ADR-0111).
        case_id=None,
        precondition_guards=[
            CheckCaseUpdateOwnerNode(
                case_id=case_id, sender_actor_id=request.actor_id
            ),
        ],
        replica_effects=[
            CaptureCaseUpdateBroadcastExclusionsNode(case_id=case_id),
            ApplyCaseUpdateNode(case_id=case_id, request=request),
        ],
        manager_effects=[BroadcastCaseUpdateNode(case_id=case_id)],
        manager_case_id=case_id,
        manager_gate_name="GuardedBroadcastCaseUpdateBT",
    )
    logger.info(
        "Created UpdateCaseBT for case=%s, actor=%s", case_id, actor_id
    )
    return root
