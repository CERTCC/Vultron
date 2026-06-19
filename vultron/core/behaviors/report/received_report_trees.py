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
from vultron.core.behaviors.case.nodes.lifecycle import (
    create_guarded_commit_case_ledger_entry_tree,
)
from vultron.core.behaviors.report.nodes.conditions import (
    CheckRMStateReceivedOrInvalid,
    CheckRMStateValid,
    EnsureEmbargoExists,
    EvaluateReportCredibility,
    EvaluateReportValidity,
)
from vultron.core.behaviors.report.nodes.emit import EmitAckReportActivity
from vultron.core.behaviors.report.nodes.rm_transitions import (
    TransitionRMtoValid,
)
from vultron.core.behaviors.report.nodes.rm_transitions import (
    TransitionCaseParticipantRMtoClosed,
    TransitionCaseParticipantRMtoInvalid,
)
from vultron.core.behaviors.report.nodes.storage import (
    StoreActivityNode,
    StoreReportNode,
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

    When ``case_id`` is provided, the guarded-commit subtree
    (``create_guarded_commit_case_ledger_entry_tree``) is appended as the
    final child so ``CheckIsCaseManagerNode`` fires when the receiving actor
    holds ``CVDRole.CASE_MANAGER``.  When ``case_id`` is ``None`` the tree
    omits the guarded commit entirely (no ledger entry is written).

    Structure::

        ValidateReportReceivedBT (Sequence)
        ├── ValidationOrSkip (Selector)
        │   ├── ValidationOrShortcut (Selector)   # try validation
        │   │   ├── CheckRMStateValid(sender_actor_id)       # idempotency exit
        │   │   └── ValidationFlow (Sequence)
        │   │       ├── CheckRMStateReceivedOrInvalid(sender_actor_id)
        │   │       ├── EvaluateReportCredibility
        │   │       ├── EvaluateReportValidity
        │   │       └── ValidationActions (Sequence)
        │   │           ├── TransitionRMtoValid(sender_actor_id)
        │   │           └── EnsureEmbargoExists
        │   └── Success("ValidationSkipped")        # fallback — commit always runs
        └── GuardedCommitOrSkip (Selector, only if case_id)
            ├── Sequence
            │   ├── CheckIsCaseManagerNode
            │   └── CommitCaseLedgerEntryNode
            └── Success("CommitSkippedNotCaseManager")

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
    validation_actions = py_trees.composites.Sequence(
        name="ValidationActions",
        memory=False,
        children=[
            TransitionRMtoValid(
                report_id=report_id,
                offer_id=offer_id,
                sender_actor_id=sender_actor_id,
            ),
            EnsureEmbargoExists(report_id=report_id),
        ],
    )

    validation_flow = py_trees.composites.Sequence(
        name="ValidationFlow",
        memory=False,
        children=[
            CheckRMStateReceivedOrInvalid(
                report_id=report_id, sender_actor_id=sender_actor_id
            ),
            EvaluateReportCredibility(report_id=report_id),
            EvaluateReportValidity(report_id=report_id),
            validation_actions,
        ],
    )

    validation_or_shortcut = py_trees.composites.Selector(
        name="ValidationOrShortcut",
        memory=False,
        children=[
            CheckRMStateValid(
                report_id=report_id, sender_actor_id=sender_actor_id
            ),
            validation_flow,
        ],
    )

    children: list[py_trees.behaviour.Behaviour] = [
        py_trees.composites.Selector(
            name="ValidationOrSkip",
            memory=False,
            children=[
                validation_or_shortcut,
                py_trees.behaviours.Success(name="ValidationSkipped"),
            ],
        )
    ]

    if case_id is not None:
        children.append(
            create_guarded_commit_case_ledger_entry_tree(case_id=case_id)
        )

    root = py_trees.composites.Sequence(
        name="ValidateReportReceivedBT",
        memory=False,
        children=children,
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

    Steps (Sequence):
    1. Store AckReport activity idempotently.
    2. Emit AckReport to CaseActor (Selector — graceful no-op if no CaseActor).
    3. Guarded commit (only when ``case_id`` is provided and the receiving
       actor holds ``CVDRole.CASE_MANAGER``).

    When running under ``actor_id=receiving_actor_id`` (ADR-0022 single-BT
    shape), step 2's ``EmitAckReportActivity`` uses the blackboard
    ``actor_id`` as sender.  On the received side (no TriggerActivityPort),
    the emit node returns FAILURE and the ``NoEmitFallback`` Success absorbs
    it — so the emit is a graceful no-op in the typical CaseActor context.

    Args:
        request: The parsed inbound domain event.
        case_id: ID of the VulnerabilityCase linked to this report.  When
            provided, a guarded-commit subtree is appended so the receiving
            CaseActor can write a canonical ledger entry.

    Returns:
        Root node of the ``AckReportReceivedBT`` Sequence.
    """
    activity_id = request.activity_id or ""
    offer_id = request.offer_id or activity_id
    report_id = request.report_id or ""

    children: list[py_trees.behaviour.Behaviour] = [
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
    ]

    if case_id is not None:
        children.append(
            create_guarded_commit_case_ledger_entry_tree(case_id=case_id)
        )

    root = py_trees.composites.Sequence(
        name="AckReportReceivedBT",
        memory=False,
        children=children,
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
