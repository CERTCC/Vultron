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
from vultron.core.behaviors.case.nodes.case_lookup import RequireCaseForReport
from vultron.core.behaviors.case.nodes.lifecycle import (
    create_receive_activity_tree,
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
from vultron.core.behaviors.report.validate_tree import (
    create_validate_report_subtree,
)

logger = logging.getLogger(__name__)


def create_validate_report_received_tree(
    report_id: str,
    offer_id: str,
    sender_actor_id: str,
    case_id: str | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the single-BT received-side tree for ValidateReport (ADR-0022).

    Composes the validate-report workflow for a received ``Accept(Offer(Report))``
    activity.  All nodes that need the message sender's identity receive
    ``sender_actor_id`` as an explicit constructor arg so the tree can run
    under ``actor_id=receiving_actor_id`` while still transitioning the
    *sender's* RM state to VALID.

    When ``case_id`` is provided, a guarded-commit subtree is inserted before
    the validation effects so receipt is recorded before any RM state
    transitions run (CLP-10-006).  Pass ``None`` to skip ledger commit.

    The validation subtree itself is built by
    :func:`~vultron.core.behaviors.report.validate_tree.create_validate_report_subtree`
    with ``emit=False`` — one definition shared with the trigger side
    (ARCH-15-004).  ``emit=False`` because the activity being handled *is* the
    ``validate-report`` message; re-emitting it would loop.

    Structure::

        ValidateReportReceivedBT (Sequence)
        ├── GuardedCommitOrSkip (Selector, only if case_id)  # receipt (CLP-10-006)
        │   ├── Sequence
        │   │   ├── CheckIsCaseManagerNode
        │   │   └── CommitCaseLedgerEntryNode
        │   └── Success("CommitSkippedNotCaseManager")
        └── ValidateReportBT (Selector)
            ├── CheckRMStateValid(sender_actor_id)      # idempotency exit
            └── ValidationFlow (Sequence)
                ├── CheckRMStateReceivedOrInvalid(sender_actor_id)
                ├── EvaluateReportCredibility
                ├── EvaluateReportValidity
                ├── RequireCaseForReport                # publishes /case_id
                ├── EnsureEmbargoExists                 # DUR-07-004
                └── ValidationActions (Sequence)
                    └── TransitionRMtoValid(sender_actor_id)

    There is no ``Success("ValidationSkipped")`` mask around the validation
    subtree any more.  It turned every validation failure into a SUCCESS the
    caller could not distinguish from a real one (ARCH-15-001) — including the
    ISSUE-2548 case where the sender's case replica had not arrived yet.

    Args:
        report_id: ID of the VulnerabilityReport being validated.
        offer_id: ID of the Offer activity that carried the report.
        sender_actor_id: Actor ID of the message sender (the validating actor).
            Used by validation nodes instead of the blackboard ``actor_id``.
        case_id: ID of the VulnerabilityCase linked to this report.  Required
            for the guarded-commit step; pass ``None`` to skip ledger commit.

    Returns:
        Root node of the ``ValidateReportReceivedBT`` Sequence.
    """
    validation = create_validate_report_subtree(
        report_id=report_id,
        offer_id=offer_id,
        sender_actor_id=sender_actor_id,
        emit=False,
    )

    root = create_receive_activity_tree(
        name="ValidateReportReceivedBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=[validation],
    )
    logger.debug(
        "Created ValidateReportReceivedBT for report=%s offer=%s sender=%s"
        " case=%s",
        report_id,
        offer_id,
        sender_actor_id,
        case_id,
    )
    return root


def create_report_received_tree(
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
    case_id: str | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the AckReportReceived workflow.

    Handles receipt of a ``Read(Offer(Report))`` (AckReport) activity.

    Steps (Sequence via :func:`create_receive_activity_tree`):

    1. Guarded commit (only when ``case_id`` is provided and the receiving
       actor holds ``CVDRole.CASE_MANAGER``) — records receipt before any
       effects run (CLP-10-006).
    2. Store AckReport activity idempotently.
    3. Emit AckReport to CaseActor (Selector — graceful no-op if no CaseActor).

    When running under ``actor_id=receiving_actor_id`` (ADR-0022 single-BT
    shape), step 3's ``EmitAckReportActivity`` uses the blackboard
    ``actor_id`` as sender.  On the received side (no TriggerActivityPort),
    the emit node returns FAILURE and the ``NoEmitFallback`` Success absorbs
    it — so the emit is a graceful no-op in the typical CaseActor context.

    Args:
        request: The parsed inbound domain event.
        case_id: ID of the VulnerabilityCase linked to this report.  When
            provided, a guarded-commit subtree is inserted first so the
            receiving CaseActor can write a canonical ledger entry.

    Returns:
        Root node of the ``AckReportReceivedBT`` Sequence.
    """
    activity_id = request.activity_id or ""
    offer_id = request.offer_id or activity_id
    report_id = request.report_id or ""

    maybe_emit = py_trees.composites.Selector(
        name="MaybeEmitAckToCaseActor",
        memory=False,
        children=[
            EmitAckReportActivity(
                offer_id=offer_id,
                report_id=report_id,
            ),
            py_trees.behaviours.Success(name="NoEmitFallback"),
        ],
    )

    root = create_receive_activity_tree(
        name="AckReportReceivedBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=[
            StoreActivityNode(
                activity_id=activity_id,
                activity_obj=request.activity,
                label="AckReport",
            ),
            maybe_emit,
        ],
    )
    logger.debug(
        "Created AckReportReceivedBT for activity=%s case=%s",
        activity_id,
        case_id,
    )
    return root


def create_close_report_received_tree(
    request: CloseReportReceivedEvent,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the CloseReportReceived workflow.

    Handles receipt of a ``Reject(VulnerabilityReport)`` (CloseReport) activity.

    Steps (Sequence):
    1. Store CloseReport activity idempotently.
    2. Resolve this actor's case for the report (``RequireCaseForReport``).
    3. Transition actor's RM state → CLOSED in that case.

    Steps 2–3 return FAILURE when the case is not in this actor's store.  They
    used to soft-pass with SUCCESS, which reported a state transition that never
    happened (ARCH-15-001, ISSUE-2548).  The stored activity in step 1 is what
    makes a later retry possible.

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
            RequireCaseForReport(report_id=request.report_id),
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
    2. Resolve this actor's case for the report (``RequireCaseForReport``).
    3. Transition actor's RM state → INVALID in that case.

    Steps 2–3 return FAILURE when the case is not in this actor's store, for the
    same reason as ``create_close_report_received_tree`` (ARCH-15-001,
    ISSUE-2548).

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
            RequireCaseForReport(report_id=request.report_id),
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
