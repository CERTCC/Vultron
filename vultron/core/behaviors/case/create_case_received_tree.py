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
    ├─ CaseOpenToExternalWrites
    ├─ SenderIsExpectedCaseCreatorNode      # sender guard (CBT-01-011, HP-01-008)
    ├─ ClassifyBootstrapRouteNode           # trusted | redelivery
    └─ BootstrapRoute (Selector)
       ├─ TrustedBootstrap (Sequence)       # CBT-01-005 / CBT-01-006
       │  ├─ BootstrapRouteIs_trusted
       │  ├─ CheckTrustedCreatorNode
       │  ├─ CheckReportReferenceNode       # CBT-01-005
       │  ├─ CheckInlineParticipantsNode
       │  ├─ HoldCarriedEmbargoNode
       │  ├─ SeedCaseReplicaNode
       │  ├─ BindReportCaseLinkNode
       │  ├─ StoreEmbeddedParticipantsNode
       │  └─ IntroduceCaseManagerToReporterNode   # CBT-01-001, ADR-0132
       ├─ RedeliveredBootstrap (Sequence)   # already accepted
       │  ├─ BootstrapRouteIs_redelivery
       │  └─ IntroduceCaseManagerToReporterNode   # retry a failed introduction
       └─ RefuseBootstrapNode               # carries the chosen route's reason

The sender guard is composed by the factory from the use case's declared
rule (HP-01-007, HP-01-008): the sender must be the actor a report case link
this receiver wrote expects the case from, or the creator of a bootstrap it
already accepted.  Any other sender is refused before anything is stored,
whatever its snapshot claims (CBT-01-011, ADR-0132).  The classifier then
only chooses between the two routes an admitted sender can take.

On the trusted route the receiver may be the report receiver, which then
introduces the CASE_MANAGER to the reporter with its own
``Create(VulnerabilityCase)`` (ADR-0132); the same node does nothing at the
reporter, which receives that introduction on the same route.  The
redelivery route runs the node again: when the first delivery seeded the
replica but failed to queue the introduction, the CASE_MANAGER's redelivery
of its ``Create`` is the only later trigger for it.

The route is chosen once by the classifier, not by re-testing a condition on
each arm, because the trusted arm's own write changes what a re-test would see.
``RefuseBootstrapNode`` is last so a route that failed is reported with its own
reason rather than with the gate of the arm tried after it.

No ledger commit (``case_id=None``): the replica this seeds is a *copy* of a
case someone else holds, and the assertions about that case reach this actor as
ledger entries.  The bootstrap is the receiver learning that the case exists.

Per specs/case-bootstrap-trust.yaml CBT-01-003 through CBT-01-007, CBT-01-012 and
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
    CheckReportReferenceNode,
    CheckTrustedCreatorNode,
    ClassifyBootstrapRouteNode,
    RefuseBootstrapNode,
    SeedCaseReplicaNode,
)
from vultron.core.behaviors.case.nodes.reporter_introduction import (
    IntroduceCaseManagerToReporterNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.replica_emit_exemptions import (
    REPORTER_INTRODUCTION,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    CaseBootstrapRequest,
    SenderCheckContext,
)
from vultron.core.services.case_replica_seeding import report_ids_of


def create_create_case_received_tree(
    case_obj: Any,
    case_id: str,
    sender_id: str,
    *,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Build the bootstrap tree for a received ``Create(VulnerabilityCase)``.

    Args:
        case_obj: The ``VulnerabilityCase`` the sender created.
        case_id: Its id.
        sender_id: The actor that sent the Create.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-008).  The receiver
            holds no case yet, so the guard is the rule's side for an
            activity that names no case this store holds.

    Returns:
        The tree root; the chosen route is on its
        :class:`~vultron.core.behaviors.case.nodes.replica_bootstrap.ClassifyBootstrapRouteNode`.
    """
    route = BootstrapRoute()
    report_ids = report_ids_of(case_obj)
    trusted = py_trees.composites.Sequence(
        name="TrustedBootstrap",
        memory=False,
        children=[
            BootstrapRouteIsNode(route, "trusted"),
            CheckTrustedCreatorNode(route, sender_id, case_id),
            CheckReportReferenceNode(route, report_ids, case_id),
            CheckInlineParticipantsNode(case_obj, case_id),
            HoldCarriedEmbargoNode(case_obj, case_id),
            SeedCaseReplicaNode(route, case_obj, case_id),
            BindReportCaseLinkNode(route, case_obj, case_id),
            StoreEmbeddedParticipantsNode(case_obj, case_id),
            IntroduceCaseManagerToReporterNode(case_id),
        ],
    )
    redelivered = py_trees.composites.Sequence(
        name="RedeliveredBootstrap",
        memory=False,
        children=[
            BootstrapRouteIsNode(route, "redelivery"),
            # Retries an introduction a first delivery failed to queue.
            IntroduceCaseManagerToReporterNode(case_id, retry=True),
        ],
    )
    arms: dict[BootstrapRouteName, py_trees.behaviour.Behaviour] = {
        "trusted": trusted,
        "redelivery": redelivered,
    }
    choose = py_trees.composites.Selector(
        name="BootstrapRoute",
        memory=False,
        children=[
            trusted,
            redelivered,
            RefuseBootstrapNode(route, arms),
        ],
    )
    return create_receive_activity_tree(
        name="CreateCaseReceivedBT",
        case_id=None,
        precondition_guards=[],
        # The receiver holds no case yet, so the context names none (the
        # tree commits nothing either); the anchor the guard reads is keyed
        # on the case the bootstrap creates (CBT-01-005).
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_id, request=CaseBootstrapRequest(case_id=case_id)
        ),
        replica_effects=[
            ClassifyBootstrapRouteNode(route, sender_id, case_id, report_ids),
            choose,
        ],
        replica_emit_exemption=REPORTER_INTRODUCTION,
    )
