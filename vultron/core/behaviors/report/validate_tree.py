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

Per specs/behavior-tree-integration.yaml BT-06 requirements.

Structure:

    ValidateReportBT (Selector)
    ├─ CheckRMStateValid                     # Early exit if already valid
    └─ ValidationFlow (Sequence)
       ├─ CheckRMStateReceivedOrInvalid       # Precondition check
       ├─ EvaluateReportCredibility           # Policy check (stub)
       ├─ EvaluateReportValidity             # Policy check (stub)
       └─ ValidationActions (Sequence)
          ├─ TransitionRMtoValid             # Vendor RM: → VALID
          └─ EnsureEmbargoExists            # Verify embargo present (DUR-07-004)

Per ADR-0015, case and participant creation now occurs at RM.RECEIVED (in
``SubmitReportReceivedUseCase`` via ``create_receive_report_case_tree``).
``ValidationActions`` only transitions the report state and confirms the
precondition (embargo) established at receipt.

``validate-report`` advances RM to VALID only.  The engage/defer decision
(RM → ACCEPTED or RM → DEFERRED) is a distinct, explicit protocol step
driven by a separate ``engage-case`` or ``defer-case`` trigger.  These are
intentionally separate: a receiver may validate a report and still choose
to defer it without ever engaging.

Phase 1 simplifications:
- No invalidation fallback (validation always succeeds)
- No information gathering loop (no data collection)
- Policy nodes are stubs (always SUCCESS)
- No InvalidateReport sequence as fallback

Future enhancements (Phase 2+):
- Add InvalidateReport fallback sequence
- Implement real policy evaluation logic
- Add information gathering workflow
"""

import logging

import py_trees

from vultron.core.behaviors.report.nodes import (
    CheckRMStateReceivedOrInvalid,
    CheckRMStateValid,
    EnsureEmbargoExists,
    EvaluateReportCredibility,
    EvaluateReportValidity,
    TransitionRMtoValid,
)
from vultron.core.behaviors.report.nodes.emit import EmitValidateReportActivity

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

    Advances RM state to VALID only.  The engage/defer decision
    (RM → ACCEPTED or RM → DEFERRED) is a separate, explicit protocol step
    that the operator must trigger via ``engage-case`` or ``defer-case``.

    Per ADR-0021 CLP-10-001: the root Selector now includes an emit node
    that sends an RmValidateReportActivity addressed to the Case Actor
    (CASE_MANAGER participant). This enables the CaseActor's inbox to receive
    the activity and execute the guarded commit (CLP-10-002, CLP-10-003).

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
        >>> from vultron.core.behaviors.bridge import BTBridge
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

    # Child sequence: All validation actions (status update + embargo check)
    validation_actions = py_trees.composites.Sequence(
        name="ValidationActions",
        memory=False,
        children=[
            TransitionRMtoValid(report_id=report_id, offer_id=offer_id),
            EnsureEmbargoExists(report_id=report_id),
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

    # Validation selector (used by both branches)
    validation_or_shortcut = py_trees.composites.Selector(
        name="ValidationOrShortcut",
        memory=False,
        children=[
            CheckRMStateValid(report_id=report_id),
            validation_flow,
        ],
    )

    # Sequence: Emit then validate (trigger-side preference)
    emit_and_validate = py_trees.composites.Sequence(
        name="EmitAndValidate",
        memory=False,
        children=[
            EmitValidateReportActivity(offer_id=offer_id, report_id=report_id),
            validation_or_shortcut,
        ],
    )

    # Fallback: just validate if emit is not available (received-side)
    # Create a separate validation selector since the first one is used above
    validation_only = py_trees.composites.Selector(
        name="ValidationOrShortcutFallback",
        memory=False,
        children=[
            CheckRMStateValid(report_id=report_id),
            py_trees.composites.Sequence(
                name="ValidationFlow",
                memory=False,
                children=[
                    CheckRMStateReceivedOrInvalid(report_id=report_id),
                    EvaluateReportCredibility(report_id=report_id),
                    EvaluateReportValidity(report_id=report_id),
                    py_trees.composites.Sequence(
                        name="ValidationActions",
                        memory=False,
                        children=[
                            TransitionRMtoValid(
                                report_id=report_id, offer_id=offer_id
                            ),
                            EnsureEmbargoExists(report_id=report_id),
                        ],
                    ),
                ],
            ),
        ],
    )

    # Root Selector: try emit+validate, fallback to validate-only
    # On trigger side: emit succeeds, validation proceeds
    # On received side: emit fails (no TriggerActivityPort), fallback validates
    root = py_trees.composites.Selector(
        name="ValidateReportBT",
        memory=False,
        children=[
            emit_and_validate,
            validation_only,
        ],
    )

    logger.info(
        f"Created ValidateReportBT for report={report_id}, offer={offer_id}"
    )
    return root
