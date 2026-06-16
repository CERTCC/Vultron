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
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.report.nodes import (
    CheckRMStateReceivedOrInvalid,
    CheckRMStateValid,
    EnsureEmbargoExists,
    EvaluateReportCredibility,
    EvaluateReportValidity,
    TransitionRMtoValid,
)

logger = logging.getLogger(__name__)


class CommitValidateReportLedgerEntryNode(DataLayerAction):
    """Commit ``validate_report`` only in the CaseActor receiver context."""

    def __init__(
        self,
        case_id: str,
        offer_id: str,
        payload_snapshot: dict[str, Any] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.offer_id = offer_id
        self.payload_snapshot = payload_snapshot or {}

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="sync_port", access=py_trees.common.Access.READ
        )

    def _receiving_actor_id(self) -> str | None:
        try:
            activity = self.blackboard.activity
        except (AttributeError, KeyError):
            return None
        return getattr(activity, "receiving_actor_id", None)

    def _sync_port(self) -> Any:
        try:
            return self.blackboard.sync_port
        except (AttributeError, KeyError):
            return None

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        from vultron.core.ports.case_persistence import CaseOutboxPersistence
        from vultron.core.use_cases._helpers import _find_case_actor_id
        from vultron.core.use_cases.triggers.sync import (
            commit_log_entry_trigger,
        )

        case_actor_id = _find_case_actor_id(self.datalayer, self.case_id)
        if case_actor_id is None:
            self.logger.warning(
                "%s: cannot resolve CaseActor for case '%s'",
                self.name,
                self.case_id,
            )
            return Status.SUCCESS

        receiving_actor_id = self._receiving_actor_id()
        if receiving_actor_id != case_actor_id:
            if receiving_actor_id is None:
                self.logger.warning(
                    "%s: missing receiving_actor_id for case '%s' — skipping"
                    " canonical validate_report commit",
                    self.name,
                    self.case_id,
                )
            return Status.SUCCESS

        commit_log_entry_trigger(
            case_id=self.case_id,
            object_id=self.offer_id,
            event_type="validate_report",
            actor_id=case_actor_id,
            dl=cast(CaseOutboxPersistence, self.datalayer),
            payload_snapshot=self.payload_snapshot,
            sync_port=self._sync_port(),
        )
        return Status.SUCCESS


def create_validate_report_tree(
    report_id: str,
    offer_id: str,
    case_id: str | None = None,
    payload_snapshot: dict[str, Any] | None = None,
) -> py_trees.behaviour.Behaviour:
    """
    Create behavior tree for report validation workflow.

    This tree follows the structure of the simulation BT in
    vultron/bt/report_management/_behaviors/validate_report.py:RMValidateBt
    with Phase 1 simplifications matching the procedural handler logic.

    Advances RM state to VALID only.  The engage/defer decision
    (RM → ACCEPTED or RM → DEFERRED) is a separate, explicit protocol step
    that the operator must trigger via ``engage-case`` or ``defer-case``.

    When *case_id* and *payload_snapshot* are supplied, a
    ``CommitValidateReportLedger`` subtree is appended to ``ValidationActions``
    so that a canonical ``validate_report`` ledger entry is written atomically
    with the RM state transition (BT-15-001).

    Args:
        report_id: ID of VulnerabilityReport to validate
        offer_id: ID of Offer activity containing the report
        case_id: URI of the associated VulnerabilityCase (required for ledger
            commit; if None the ledger subtree is omitted)
        payload_snapshot: Pre-built AS2 payload snapshot for the ledger entry

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

    validation_action_children = [
        TransitionRMtoValid(report_id=report_id, offer_id=offer_id),
        EnsureEmbargoExists(report_id=report_id),
    ]
    if case_id is not None:
        validation_action_children.append(
            CommitValidateReportLedgerEntryNode(
                case_id=case_id,
                offer_id=offer_id,
                payload_snapshot=payload_snapshot,
            )
        )

    # Child sequence: All validation actions (status update + embargo check +
    # optional ledger commit)
    validation_actions = py_trees.composites.Sequence(
        name="ValidationActions",
        memory=False,
        children=validation_action_children,
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

    logger.info(
        f"Created ValidateReportBT for report={report_id}, offer={offer_id}"
    )
    return root
