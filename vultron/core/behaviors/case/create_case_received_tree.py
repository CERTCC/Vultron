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

"""Tree for a received ``Create(VulnerabilityCase)`` replica bootstrap (#3874).

Structure (after intake, which the shared factory supplies first)::

    CreateCaseReceivedBT (Sequence)
    ├─ IntakeReceivedActivityNode
    ├─ ClassifyBootstrapRouteNode           # trusted | redelivery | direct
    └─ BootstrapRoute (Selector)
       ├─ TrustedBootstrap (Sequence)       # CBT-01-005 / CBT-01-006
       │  ├─ BootstrapRouteIs_trusted
       │  ├─ CheckTrustedCreatorNode
       │  ├─ CheckInlineParticipantsNode
       │  ├─ HoldCarriedEmbargoNode
       │  ├─ SeedCaseReplicaNode
       │  ├─ BindReportCaseLinkNode
       │  └─ StoreEmbeddedParticipantsNode
       ├─ RedeliveredBootstrap (Sequence)   # already accepted: nothing to do
       │  ├─ BootstrapRouteIs_redelivery
       │  └─ AcceptRedeliveredBootstrap
       ├─ DirectParticipantBootstrap (Sequence)   # ADR-0041 AC-5
       │  ├─ BootstrapRouteIs_direct
       │  ├─ CheckSenderIsSnapshotManagerNode
       │  ├─ HoldCarriedEmbargoNode
       │  ├─ SeedCaseReplicaNode
       │  └─ StoreEmbeddedParticipantsNode
       └─ RefuseBootstrapNode               # carries the chosen route's reason

The route is chosen once by the classifier, not by re-testing a condition on
each arm, because the trusted arm's own write changes what a re-test would see.
``RefuseBootstrapNode`` is last so a route that failed is reported with its own
reason rather than with the gate of the arm tried after it.

No ledger commit (``case_id=None``): the replica this seeds is a *copy* of a
case someone else holds, and the assertions about that case reach this actor as
ledger entries.  The bootstrap is the receiver learning that the case exists.

Per specs/case-bootstrap-trust.yaml CBT-01-003 through CBT-01-007 and
specs/case-ledger-processing.yaml CLP-10-005, CLP-10-007, CLP-10-017.
"""

from typing import Any

import py_trees

from vultron.core.behaviors.case.nodes.carried_snapshot import (
    HoldCarriedEmbargoNode,
    StoreEmbeddedParticipantsNode,
)
from vultron.core.behaviors.case.nodes.replica_bootstrap import (
    BindReportCaseLinkNode,
    BootstrapRoute,
    BootstrapRouteIsNode,
    BootstrapRouteName,
    CheckInlineParticipantsNode,
    CheckSenderIsSnapshotManagerNode,
    CheckTrustedCreatorNode,
    ClassifyBootstrapRouteNode,
    RefuseBootstrapNode,
    SeedCaseReplicaNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)


def create_create_case_received_tree(
    case_obj: Any, case_id: str, sender_id: str
) -> py_trees.composites.Sequence:
    """Build the bootstrap tree for a received ``Create(VulnerabilityCase)``.

    Args:
        case_obj: The ``VulnerabilityCase`` the sender created.
        case_id: Its id.
        sender_id: The actor that sent the Create.

    Returns:
        The tree root; the chosen route is on its
        :class:`~vultron.core.behaviors.case.nodes.replica_bootstrap.ClassifyBootstrapRouteNode`.
    """
    route = BootstrapRoute()
    trusted = py_trees.composites.Sequence(
        name="TrustedBootstrap",
        memory=False,
        children=[
            BootstrapRouteIsNode(route, "trusted"),
            CheckTrustedCreatorNode(route, sender_id, case_id),
            CheckInlineParticipantsNode(case_obj, case_id),
            HoldCarriedEmbargoNode(case_obj, case_id),
            SeedCaseReplicaNode(route, case_obj, case_id),
            BindReportCaseLinkNode(route, case_obj, case_id),
            StoreEmbeddedParticipantsNode(case_obj, case_id),
        ],
    )
    redelivered = py_trees.composites.Sequence(
        name="RedeliveredBootstrap",
        memory=False,
        children=[
            BootstrapRouteIsNode(route, "redelivery"),
            py_trees.behaviours.Success(name="AcceptRedeliveredBootstrap"),
        ],
    )
    direct = py_trees.composites.Sequence(
        name="DirectParticipantBootstrap",
        memory=False,
        children=[
            BootstrapRouteIsNode(route, "direct"),
            CheckSenderIsSnapshotManagerNode(case_obj, sender_id, case_id),
            HoldCarriedEmbargoNode(case_obj, case_id),
            SeedCaseReplicaNode(route, case_obj, case_id),
            StoreEmbeddedParticipantsNode(case_obj, case_id),
        ],
    )
    arms: dict[BootstrapRouteName, py_trees.behaviour.Behaviour] = {
        "trusted": trusted,
        "redelivery": redelivered,
        "direct": direct,
    }
    choose = py_trees.composites.Selector(
        name="BootstrapRoute",
        memory=False,
        children=[
            trusted,
            redelivered,
            direct,
            RefuseBootstrapNode(route, arms),
        ],
    )
    return create_receive_activity_tree(
        name="CreateCaseReceivedBT",
        case_id=None,
        precondition_guards=[],
        replica_effects=[
            ClassifyBootstrapRouteNode(route, sender_id, case_id),
            choose,
        ],
    )
