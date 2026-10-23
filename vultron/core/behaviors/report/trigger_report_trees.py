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

"""Behavior tree factories for report-lifecycle trigger use cases.

Each factory produces a ``py_trees.composites.Sequence`` that implements the
outbound protocol handling for one of the report-lifecycle trigger
operations:

- ``AckReport``        — emit Read(Offer(Report)) (RK) to the reporter
- ``InvalidateReport`` — emit TentativeReject activity + transition RM → INVALID
- ``RejectReport``     — guard (report in no case) + guard (RM may close) +
                         emit CloseReport activity + transition RM → CLOSED

The ``CloseReport`` emitter fails closed when the report belongs to a case:
an actor closes its part in a case by ``Leave(VulnerabilityCase)``, through the
``leave-case`` trigger (TRIG-13-001), and no actor sends ``Close(Report)`` for a
report a case holds (CM-23-019).

Trees are run via ``BTBridge.execute_with_setup()`` in the corresponding
trigger use case.

Per issue #849 AC-1 through AC-3 and specs/behavior-tree-integration.yaml
BT-15-001, BT-15-002.
"""

import logging

import py_trees

from vultron.core.behaviors.report.nodes.close_conditions import (
    CheckReportClosable,
    CheckReportHasNoCase,
)
from vultron.core.behaviors.report.nodes.emit import (
    EmitAckReportActivity,
    EmitCloseReportActivity,
    EmitInvalidateReportActivity,
    EmitSubmitReportActivity,
)
from vultron.core.behaviors.report.nodes.rm_transitions import (
    TransitionRMtoClosed,
    TransitionRMtoInvalid,
)

logger = logging.getLogger(__name__)


def create_ack_report_trigger_tree(
    offer_id: str,
    report_id: str,
    note: str | None = None,
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the ack-report trigger workflow.

    Emits ``RmReadReportActivity`` (``Read(Offer(Report))``, RK) to the
    reporter (RMB-08-003).  An acknowledgement moves no RM state, so the tree
    has no transition node.

    Structure::

        AckReportTriggerBT (Sequence)
        └─ EmitAckReportActivity  # emit RK to the Offer's actor + queue

    Args:
        offer_id: ID of the Offer being acknowledged.
        report_id: ID of the VulnerabilityReport.
        note: Optional free text carried as the RK's ``content``
            (TRIG-03-003).
        captured: Optional dict; ``captured["activity"]`` is set to the
            serialised activity dict on success (DL-06-001).

    Returns:
        Root node of the ``AckReportTriggerBT`` Sequence.
    """
    root = py_trees.composites.Sequence(
        name="AckReportTriggerBT",
        memory=False,
        children=[
            EmitAckReportActivity(
                offer_id=offer_id,
                report_id=report_id,
                content=note,
                captured=captured,
            ),
        ],
    )
    logger.debug(
        "Created AckReportTriggerBT for offer=%s report=%s",
        offer_id,
        report_id,
    )
    return root


def create_invalidate_report_trigger_tree(
    offer_id: str,
    report_id: str,
    captured: dict | None = None,
    sender_actor_id: str | None = None,
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
        captured: Optional dict; ``captured["activity"]`` is set to the
            serialised activity dict on success (DL-06-001, AC-1).

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
                captured=captured,
            ),
            TransitionRMtoInvalid(
                report_id=report_id,
                offer_id=offer_id,
                sender_actor_id=sender_actor_id,
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
    captured: dict | None = None,
    sender_actor_id: str | None = None,
    result_out: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the reject-report trigger workflow.

    Emits ``RmCloseReportActivity`` (hard-close/Reject) and records the
    actor's RM state as CLOSED for the report.  It does NOT refuse a prior
    CLOSED state — a repeat hard-reject is a status confirmation.

    A report that belongs to a case is refused first, before anything is
    emitted: its Case Owner closes the case by ``Leave(VulnerabilityCase)``
    (CM-23-019).

    The hard-reject writes ``CLOSED`` only through a transition the RM table
    permits: from *Received* it is the ``R → C`` transition (RMB-14-004), and
    from *Valid*, which has no close edge (VP-02-004), it is refused before
    anything is emitted.

    Structure::

        RejectReportTriggerBT (Sequence)
        ├─ CheckReportHasNoCase     # guard: FAILURE if a case holds the report
        ├─ CheckReportClosable      # guard: FAILURE if RM has no close edge
        ├─ EmitCloseReportActivity  # emit activity + queue in outbox
        └─ TransitionRMtoClosed     # persist report-phase RM.CLOSED

    Args:
        offer_id: ID of the Offer being rejected.
        report_id: ID of the VulnerabilityReport.
        captured: Optional dict; ``captured["activity"]`` is set to the
            serialised activity dict on success (DL-06-001, AC-1).
        sender_actor_id: The rejecting actor.
        result_out: Optional mutable dict; ``result_out["error"]`` is set to a
            ``VultronInvalidStateTransitionError`` when a case holds the
            report or the report's RM state has no close edge.

    Returns:
        Root node of the ``RejectReportTriggerBT`` Sequence.
    """
    root = py_trees.composites.Sequence(
        name="RejectReportTriggerBT",
        memory=False,
        children=[
            CheckReportHasNoCase(report_id=report_id, result_out=result_out),
            CheckReportClosable(report_id=report_id, result_out=result_out),
            EmitCloseReportActivity(
                offer_id=offer_id,
                report_id=report_id,
                captured=captured,
            ),
            TransitionRMtoClosed(
                report_id=report_id,
                offer_id=offer_id,
                sender_actor_id=sender_actor_id,
            ),
        ],
    )
    logger.debug(
        "Created RejectReportTriggerBT for offer=%s report=%s",
        offer_id,
        report_id,
    )
    return root


def submit_report_trigger_bt(
    report_id: str,
    recipient_id: str,
    captured: dict | None = None,
    proposed_embargo_id: str | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the submit-report trigger workflow.

    Emits ``Offer(VulnerabilityReport)`` addressed to *recipient_id* and
    queues the offer ID in the actor's outbox.  When *proposed_embargo_id*
    names the Reporter's stored ``EmbargoEvent`` for the report, the Offer
    carries it as ``proposedEmbargo`` (EP-04-004).

    Structure::

        SubmitReportTriggerBT (Sequence)
        └─ EmitSubmitReportActivity  # emit offer + queue in outbox

    Args:
        report_id: ID of the already-persisted VulnerabilityReport.
        recipient_id: Actor URI to send the offer to.
        captured: Optional dict; ``captured["offer"]`` is set to the
            serialised offer dict on success.
        proposed_embargo_id: ID of the Reporter's stored ``EmbargoEvent``
            proposing terms for the report, or ``None`` for no proposal.

    Returns:
        Root node of the ``SubmitReportTriggerBT`` Sequence.
    """
    root = py_trees.composites.Sequence(
        name="SubmitReportTriggerBT",
        memory=False,
        children=[
            EmitSubmitReportActivity(
                report_id=report_id,
                recipient_id=recipient_id,
                captured=captured,
                proposed_embargo_id=proposed_embargo_id,
            ),
        ],
    )
    logger.debug(
        "Created SubmitReportTriggerBT for report=%s recipient=%s",
        report_id,
        recipient_id,
    )
    return root
