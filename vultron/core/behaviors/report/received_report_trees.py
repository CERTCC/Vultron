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
Behavior tree factories for received-side report use cases.

Each factory produces a ``py_trees.composites.Sequence`` that implements the
inbound protocol handling for one of the four report-lifecycle activities:

- ``CreateReport`` — store VulnerabilityReport + CreateReport activity
- ``AckReport``    — store AckReport activity
- ``CloseReport``  — store CloseReport activity + transition RM → CLOSED
- ``InvalidateReport`` — store InvalidateReport activity + RM → INVALID

Trees are run via ``BTBridge.execute_with_setup()`` in the corresponding use
case.

Per issue #759 AC-1 through AC-4.
"""

import logging

import py_trees

from vultron.core.models.events.report import (
    AckReportReceivedEvent,
    CloseReportReceivedEvent,
    CreateReportReceivedEvent,
    InvalidateReportReceivedEvent,
)
from vultron.core.behaviors.report.nodes.emit import EmitAckReportActivity
from vultron.core.behaviors.report.nodes.rm_transitions import (
    TransitionCaseParticipantRMtoClosed,
    TransitionCaseParticipantRMtoInvalid,
)
from vultron.core.behaviors.report.nodes.storage import (
    StoreActivityNode,
    StoreReportNode,
)

logger = logging.getLogger(__name__)


def create_create_report_received_tree(
    request: CreateReportReceivedEvent,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the CreateReportReceived workflow.

    Handles receipt of a ``Create(VulnerabilityReport)`` activity.

    Steps (Sequence):
    1. Store VulnerabilityReport idempotently.
    2. Store CreateReport activity idempotently.

    Args:
        request: The parsed inbound domain event.

    Returns:
        Root node of the ``CreateReportReceivedBT`` Sequence.
    """
    report_id = request.report_id or ""
    activity_id = request.activity_id or ""

    root = py_trees.composites.Sequence(
        name="CreateReportReceivedBT",
        memory=False,
        children=[
            StoreReportNode(
                report_id=report_id,
                report_obj=request.report,
            ),
            StoreActivityNode(
                activity_id=activity_id,
                activity_obj=request.activity,
                label="CreateReport",
            ),
        ],
    )
    logger.debug(
        "Created CreateReportReceivedBT for report=%s activity=%s",
        report_id,
        activity_id,
    )
    return root


def create_ack_report_received_tree(
    request: AckReportReceivedEvent,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the AckReportReceived workflow.

    Handles receipt of a ``Read(Offer(Report))`` (AckReport) activity.

    Steps (Sequence):
    1. Store AckReport activity idempotently.
    2. Emit AckReport to CaseActor (Selector — graceful no-op if no CaseActor).

    Args:
        request: The parsed inbound domain event.

    Returns:
        Root node of the ``AckReportReceivedBT`` Sequence.
    """
    activity_id = request.activity_id or ""
    offer_id = request.offer_id or activity_id
    report_id = request.report_id or ""

    root = py_trees.composites.Sequence(
        name="AckReportReceivedBT",
        memory=False,
        children=[
            StoreActivityNode(
                activity_id=activity_id,
                activity_obj=request.activity,
                label="AckReport",
            ),
            py_trees.composites.Selector(
                name="MaybeEmitAckToCaseActor",
                memory=False,
                children=[
                    EmitAckReportActivity(
                        offer_id=offer_id,
                        report_id=report_id,
                    ),
                    py_trees.behaviours.Success(name="NoEmitFallback"),
                ],
            ),
        ],
    )
    logger.debug(
        "Created AckReportReceivedBT for activity=%s",
        activity_id,
    )
    return root


def create_close_report_received_tree(
    request: CloseReportReceivedEvent,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the CloseReportReceived workflow.

    Handles receipt of a ``Reject(VulnerabilityReport)`` (CloseReport) activity.

    Steps (Sequence):
    1. Store CloseReport activity idempotently.
    2. Transition actor's RM state → CLOSED in the associated case (soft pass
       if no case is found).

    Args:
        request: The parsed inbound domain event.

    Returns:
        Root node of the ``CloseReportReceivedBT`` Sequence.
    """
    activity_id = request.activity_id or ""

    root = py_trees.composites.Sequence(
        name="CloseReportReceivedBT",
        memory=False,
        children=[
            StoreActivityNode(
                activity_id=activity_id,
                activity_obj=request.activity,
                label="CloseReport",
            ),
            TransitionCaseParticipantRMtoClosed(
                report_id=request.report_id,
            ),
        ],
    )
    logger.debug(
        "Created CloseReportReceivedBT for report=%s activity=%s",
        request.report_id,
        activity_id,
    )
    return root


def create_invalidate_report_received_tree(
    request: InvalidateReportReceivedEvent,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the InvalidateReportReceived workflow.

    Handles receipt of a ``TentativeReject(VulnerabilityReport)``
    (InvalidateReport) activity.

    Steps (Sequence):
    1. Store InvalidateReport activity idempotently.
    2. Transition actor's RM state → INVALID in the associated case (soft
       pass if no case is found).

    Args:
        request: The parsed inbound domain event.

    Returns:
        Root node of the ``InvalidateReportReceivedBT`` Sequence.
    """
    activity_id = request.activity_id or ""

    root = py_trees.composites.Sequence(
        name="InvalidateReportReceivedBT",
        memory=False,
        children=[
            StoreActivityNode(
                activity_id=activity_id,
                activity_obj=request.activity,
                label="InvalidateReport",
            ),
            TransitionCaseParticipantRMtoInvalid(
                report_id=request.report_id,
            ),
        ],
    )
    logger.debug(
        "Created InvalidateReportReceivedBT for report=%s activity=%s",
        request.report_id,
        activity_id,
    )
    return root
