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
Report validation behavior tree composition.

This module composes the report validation workflow as a behavior tree,
integrating condition, action, and policy nodes from the nodes module.

Per specs/behavior-tree-integration.md BT-06 requirements.

Structure (Phase 1 - Minimal Match to Procedural Handler):

    ValidateReportBT (Selector)
    ├─ CheckRMStateValid                 # Early exit if already valid
    └─ ValidationFlow (Sequence)
       ├─ CheckRMStateReceivedOrInvalid  # Precondition check
       ├─ EvaluateReportCredibility      # Policy check (stub)
       ├─ EvaluateReportValidity         # Policy check (stub)
       └─ ValidationActions (Sequence)
          ├─ TransitionRMtoValid         # Update statuses
          ├─ CreateCaseNode              # Create case object
          ├─ CreateCaseActivity          # Generate CreateCase activity
          └─ UpdateActorOutbox           # Add to outbox

Phase 1 simplifications:
- No invalidation fallback (validation always succeeds)
- No information gathering loop (no data collection)
- Policy nodes are stubs (always SUCCESS)
- No InvalidateReport sequence as fallback

Future enhancements (Phase 2+):
- Add InvalidateReport fallback sequence
- Implement real policy evaluation logic
- Add information gathering workflow
- Add message emission nodes
"""

import logging

import py_trees

from vultron.behaviors.report.nodes import (
    CheckRMStateReceivedOrInvalid,
    CheckRMStateValid,
    CreateCaseActivity,
    CreateCaseNode,
    EvaluateReportCredibility,
    EvaluateReportValidity,
    TransitionRMtoValid,
    UpdateActorOutbox,
)

logger = logging.getLogger(__name__)


def create_validate_report_tree(
    report_id: str,
    offer_id: str,
) -> py_trees.behaviour.Behaviour:
    """
    Create behavior tree for report validation workflow.

    This tree follows the structure of the simulation BT in
    vultron/bt/report_management/_behaviors/validate_report.py:RMValidateBt
    with Phase 1 simplifications matching the procedural handler logic.

    Args:
        report_id: ID of VulnerabilityReport to validate
        offer_id: ID of Offer activity containing the report

    Returns:
        Root node of the validation behavior tree (Selector)

    Example:
        >>> tree = create_validate_report_tree(
        ...     report_id="https://example.org/reports/CVE-2024-001",
        ...     offer_id="https://example.org/activities/offer-123"
        ... )
        >>> from vultron.behaviors.bridge import BTBridge
        >>> bridge = BTBridge()
        >>> result = bridge.execute_with_setup(
        ...     tree,
        ...     actor_id="https://example.org/actors/vendor",
        ...     datalayer=get_datalayer()
        ... )
        >>> print(result.status)
        Status.SUCCESS
    """
    # Phase 1: Match procedural handler logic
    # Future: Add InvalidateReport fallback per simulation BT

    # Child sequence: All validation actions (status updates, case creation, outbox)
    validation_actions = py_trees.composites.Sequence(
        name="ValidationActions",
        memory=False,
        children=[
            TransitionRMtoValid(report_id=report_id, offer_id=offer_id),
            CreateCaseNode(report_id=report_id),
            CreateCaseActivity(report_id=report_id, offer_id=offer_id),
            UpdateActorOutbox(),
        ],
    )

    # Child sequence: Precondition checks + policy evaluation + actions
    validation_flow = py_trees.composites.Sequence(
        name="ValidationFlow",
        memory=False,
        children=[
            CheckRMStateReceivedOrInvalid(report_id=report_id),
            EvaluateReportCredibility(report_id=report_id),
            EvaluateReportValidity(report_id=report_id),
            validation_actions,
        ],
    )

    # Root selector: Early exit if valid OR run full validation flow
    root = py_trees.composites.Selector(
        name="ValidateReportBT",
        memory=False,
        children=[
            CheckRMStateValid(report_id=report_id),
            validation_flow,
        ],
    )

    logger.debug(
        f"Created ValidateReportBT for report={report_id}, offer={offer_id}"
    )
    return root
