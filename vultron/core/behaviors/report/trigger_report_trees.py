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
Behavior tree factories for report-lifecycle trigger use cases.

Each factory produces a ``py_trees.composites.Sequence`` that implements the
outbound protocol handling for one of the three report-lifecycle trigger
operations:

- ``InvalidateReport`` — emit TentativeReject activity + transition RM → INVALID
- ``RejectReport``     — emit CloseReport activity + transition RM → CLOSED
- ``CloseReport``      — guard (not already closed) + emit CloseReport + RM → CLOSED

Trees are run via ``BTBridge.execute_with_setup()`` in the corresponding
trigger use case.

Per issue #849 AC-1 through AC-3 and specs/behavior-tree-integration.yaml
BT-15-001, BT-15-002.
"""

import logging

import py_trees

from vultron.core.behaviors.report.nodes.conditions import CheckReportNotClosed
from vultron.core.behaviors.report.nodes.emit import (
    EmitCloseReportActivity,
    EmitInvalidateReportActivity,
)
from vultron.core.behaviors.report.nodes.rm_transitions import (
    TransitionRMtoClosed,
    TransitionRMtoInvalid,
)

logger = logging.getLogger(__name__)


def create_invalidate_report_trigger_tree(
    offer_id: str,
    report_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the invalidate-report trigger workflow.

    Emits ``RmInvalidateReportActivity`` (TentativeReject) and records the
    actor's RM state as INVALID for the report.

    Structure::

        InvalidateReportTriggerBT (Sequence)
        ├─ EmitInvalidateReportActivity  # emit activity + queue in outbox
        └─ TransitionRMtoInvalid         # persist report-phase RM.INVALID

    Args:
        offer_id: ID of the Offer being invalidated.
        report_id: ID of the VulnerabilityReport.

    Returns:
        Root node of the ``InvalidateReportTriggerBT`` Sequence.
    """
    root = py_trees.composites.Sequence(
        name="InvalidateReportTriggerBT",
        memory=False,
        children=[
            EmitInvalidateReportActivity(
                offer_id=offer_id,
                report_id=report_id,
            ),
            TransitionRMtoInvalid(
                report_id=report_id,
                offer_id=offer_id,
            ),
        ],
    )
    logger.debug(
        "Created InvalidateReportTriggerBT for offer=%s report=%s",
        offer_id,
        report_id,
    )
    return root


def create_reject_report_trigger_tree(
    offer_id: str,
    report_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the reject-report trigger workflow.

    Emits ``RmCloseReportActivity`` (hard-close/Reject) and records the
    actor's RM state as CLOSED for the report.  Unlike the close-report
    workflow, this path does NOT check for a prior CLOSED state — callers
    can hard-reject an offer regardless of its current status.

    Structure::

        RejectReportTriggerBT (Sequence)
        ├─ EmitCloseReportActivity  # emit activity + queue in outbox
        └─ TransitionRMtoClosed     # persist report-phase RM.CLOSED

    Args:
        offer_id: ID of the Offer being rejected.
        report_id: ID of the VulnerabilityReport.

    Returns:
        Root node of the ``RejectReportTriggerBT`` Sequence.
    """
    root = py_trees.composites.Sequence(
        name="RejectReportTriggerBT",
        memory=False,
        children=[
            EmitCloseReportActivity(
                offer_id=offer_id,
                report_id=report_id,
            ),
            TransitionRMtoClosed(
                report_id=report_id,
                offer_id=offer_id,
            ),
        ],
    )
    logger.debug(
        "Created RejectReportTriggerBT for offer=%s report=%s",
        offer_id,
        report_id,
    )
    return root


def create_close_report_trigger_tree(
    offer_id: str,
    report_id: str,
    result_out: dict,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the close-report trigger workflow.

    Guards against duplicate-close, emits ``RmCloseReportActivity``, and
    records the actor's RM state as CLOSED.  On a duplicate-close attempt
    ``CheckReportNotClosed`` writes a
    :class:`~vultron.errors.VultronInvalidStateTransitionError` into
    ``result_out["error"]`` so the calling use case can re-raise the domain
    exception.

    Structure::

        CloseReportTriggerBT (Sequence)
        ├─ CheckReportNotClosed     # guard: FAILURE + error if already CLOSED
        ├─ EmitCloseReportActivity  # emit activity + queue in outbox
        └─ TransitionRMtoClosed     # persist report-phase RM.CLOSED

    Per issue #849 AC-3: the duplicate-close guard is a BT condition node, not
    a procedural ``raise`` in ``execute()``.

    Args:
        offer_id: ID of the Offer being closed.
        report_id: ID of the VulnerabilityReport.
        result_out: Mutable dict for surfacing domain errors back to the caller.
            ``result_out["error"]`` is set to a
            ``VultronInvalidStateTransitionError`` when the report is already
            closed.

    Returns:
        Root node of the ``CloseReportTriggerBT`` Sequence.
    """
    root = py_trees.composites.Sequence(
        name="CloseReportTriggerBT",
        memory=False,
        children=[
            CheckReportNotClosed(
                report_id=report_id,
                result_out=result_out,
            ),
            EmitCloseReportActivity(
                offer_id=offer_id,
                report_id=report_id,
            ),
            TransitionRMtoClosed(
                report_id=report_id,
                offer_id=offer_id,
            ),
        ],
    )
    logger.debug(
        "Created CloseReportTriggerBT for offer=%s report=%s",
        offer_id,
        report_id,
    )
    return root
