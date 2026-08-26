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

This module composes the vendor-side workflow that runs when a vendor receives
a vulnerability report (RM.RECEIVED).  Per ADR-0041 the vendor MUST NOT create
a ``VulnerabilityCase`` locally; instead it:

1. Writes a pending ``VultronReportCaseLink`` marker recording the expected
   CaseActor that will send ``Create(VulnerabilityCase)`` in response.
2. Sends ``Create(as_CaseProposal)`` to the CaseActor service so the CaseActor
   can create the canonical case and respond with ``Create(VulnerabilityCase)``.

The local ``VulnerabilityCase`` replica is seeded later by
``CreateCaseReceivedUseCase`` when ``Create(VulnerabilityCase)`` arrives from
the CaseActor — see ``vultron/core/use_cases/received/case/create.py``.

Structure (ADR-0041):

    ReceiveReportCaseBT (Sequence)
    ├─ CheckAutoCaseCreationEnabledNode       # Gate on auto_create_case policy
    └─ ReceiveReportCaseSelector (Selector)
       ├─ CheckPendingProposalExistsForReport # Early exit if proposal already sent
       └─ ReceiveReportProposalFlow (Sequence)
          ├─ EnsureCaseActorHostedNode        # CaseActor record in its own store
          ├─ WritePendingReportCaseLinkNode   # VultronReportCaseLink(case_id=None)
          └─ ProposeReportCaseToActorNode     # Create(as_CaseProposal) → CaseActor

Per ADR-0041 and specs/case-proposal.yaml CP-04-001, CP-04-002.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes import (
    CheckAutoCaseCreationEnabledNode,
    CheckPendingProposalExistsForReport,
    EnsureCaseActorHostedNode,
    ProposeReportCaseToActorNode,
    WritePendingReportCaseLinkNode,
)
from vultron.config.actor import ActorConfig

logger = logging.getLogger(__name__)


def create_receive_report_case_tree(
    report_id: str,
    offer_id: str,
    reporter_actor_id: str,
    actor_config: ActorConfig | None = None,
) -> py_trees.behaviour.Behaviour:
    """
    Create the vendor-side behavior tree for report receipt (ADR-0041).

    Per ADR-0041, the vendor no longer creates a ``VulnerabilityCase`` at
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
            CheckPendingProposalExistsForReport(report_id=report_id),
            receive_report_proposal_flow,
        ],
    )

    root = py_trees.composites.Sequence(
        name="ReceiveReportCaseBT",
        memory=False,
        children=[
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
