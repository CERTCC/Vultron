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
Receive-report case-proposal behavior tree composition (ADR-0041).

This module composes the receiver-side workflow that runs when an actor
receives a vulnerability report (RM.RECEIVED) and so becomes the case's
prospective CASE_OWNER — a Vendor or a Coordinator alike.  Per ADR-0041 the
receiver MUST NOT create a ``VulnerabilityCase`` locally; instead it:

1. Writes a pending ``VultronReportCaseLink`` marker recording the expected
   CaseActor that will send ``Create(VulnerabilityCase)`` in response.
2. Sends ``Create(as_CaseProposal)`` to the CaseActor service so the CaseActor
   can create the canonical case and respond with ``Create(VulnerabilityCase)``.

The local ``VulnerabilityCase`` replica is seeded later by
``CreateCaseReceivedUseCase`` when ``Create(VulnerabilityCase)`` arrives from
the CaseActor — see ``vultron/core/use_cases/received/case/create.py``.

Structure (ADR-0041):

    ReceiveReportCaseBT (Sequence)
    ├─ IntakeReceivedActivityNode             # Archive the Offer (CLP-10-017)
    ├─ [received_effects]                     # Keep report/Offer/record, guard
    ├─ CheckAutoCaseCreationEnabledNode       # Gate on auto_create_case policy
    └─ ReceiveReportCaseSelector (Selector)
       ├─ CheckProposalAlreadySentForReport # Early exit if proposal already sent
       └─ ReceiveReportProposalFlow (Sequence)
          ├─ EnsureCaseActorHostedNode        # CaseActor record in its own store
          ├─ WritePendingReportCaseLinkNode   # VultronReportCaseLink(case_id=None)
          └─ ProposeReportCaseToActorNode     # Create(as_CaseProposal) → CaseActor

Per ADR-0041 and specs/case-proposal.yaml CP-04-001, CP-04-002.
"""

import logging
from collections.abc import Sequence

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes import (
    CheckAutoCaseCreationEnabledNode,
    CheckProposalAlreadySentForReport,
    EnsureCaseActorHostedNode,
    ProposeReportCaseToActorNode,
    WritePendingReportCaseLinkNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)

logger = logging.getLogger(__name__)


def create_receive_report_case_tree(
    report_id: str,
    offer_id: str,
    reporter_actor_id: str,
    actor_config: ActorConfig | None = None,
    received_effects: Sequence[py_trees.behaviour.Behaviour] = (),
) -> py_trees.behaviour.Behaviour:
    """
    Create the receiver-side behavior tree for report receipt (ADR-0041).

    Per ADR-0041, the report receiver no longer creates a ``VulnerabilityCase`` at
    report receipt.  This tree writes a pending ``VultronReportCaseLink``
    and sends ``Create(as_CaseProposal)`` to the CaseActor service.  The
    ``VulnerabilityCase`` replica is seeded when ``Create(VulnerabilityCase)``
    arrives from the CaseActor.

    Args:
        report_id: ID of the ``VulnerabilityReport`` to link to the proposal.
        offer_id: ID of the ``Offer`` activity that delivered the report.
                  Currently unused by the slimmed tree but retained for
                  API compatibility with callers.
        reporter_actor_id: Actor ID of the party who submitted the report.
                           Currently unused by the slimmed tree but retained
                           for API compatibility.
        actor_config: Optional actor configuration.  Passed to
                      ``CheckAutoCaseCreationEnabledNode`` for the
                      ``auto_create_case`` policy gate (CM-15-001).
        received_effects: Effect nodes that keep what the Offer carried (the
                          report, the Offer, the offer record) and the
                          addressing guard; they run after intake and ahead
                          of the policy gate, so a receiver that opts out of
                          case creation still holds them (CM-15-001,
                          CM-15-005).  See
                          :func:`~vultron.core.behaviors.case.nodes.submit_report.submit_report_received_effects`.

    Returns:
        Root node of the receive-report proposal behavior tree.

    Example:
        >>> tree = create_receive_report_case_tree(
        ...     report_id="https://example.org/reports/CVE-2024-001",
        ...     offer_id="https://example.org/activities/offer-123",
        ...     reporter_actor_id="https://example.org/actors/reporter",
        ... )
        >>> from vultron.core.behaviors.bridge import BTBridge
        >>> bridge = BTBridge()
        >>> result = bridge.execute_with_setup(
        ...     tree,
        ...     actor_id="https://example.org/actors/vendor",
        ... )
        >>> print(result.status)
        Status.SUCCESS
    """
    receive_report_proposal_flow = py_trees.composites.Sequence(
        name="ReceiveReportProposalFlow",
        memory=False,
        children=[
            EnsureCaseActorHostedNode(),
            WritePendingReportCaseLinkNode(report_id=report_id),
            ProposeReportCaseToActorNode(report_id=report_id),
        ],
    )

    case_creation_selector = py_trees.composites.Selector(
        name="ReceiveReportCaseSelector",
        memory=False,
        children=[
            CheckProposalAlreadySentForReport(report_id=report_id),
            receive_report_proposal_flow,
        ],
    )

    root = create_receive_activity_tree(
        name="ReceiveReportCaseBT",
        case_id=None,
        precondition_guards=[],
        effect_nodes=[
            *received_effects,
            CheckAutoCaseCreationEnabledNode(actor_config=actor_config),
            case_creation_selector,
        ],
    )

    logger.info(
        "Created ReceiveReportCaseBT for report=%s, offer=%s, reporter=%s",
        report_id,
        offer_id,
        reporter_actor_id,
    )
    return root


def create_keep_offer_without_report_tree(
    received_effects: Sequence[py_trees.behaviour.Behaviour],
) -> py_trees.behaviour.Behaviour:
    """Create the tree for an ``Offer`` that names no report.

    There is no case to propose, so the receiver only archives the Offer
    (intake) and keeps what it carried (CM-15-001).
    """
    return create_receive_activity_tree(
        name="KeepOfferWithoutReportBT",
        case_id=None,
        precondition_guards=[],
        effect_nodes=list(received_effects),
    )
