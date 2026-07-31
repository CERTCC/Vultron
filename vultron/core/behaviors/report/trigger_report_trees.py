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

- ``InvalidateReport`` — emit TentativeReject activity + transition RM → INVALID
- ``RejectReport``     — emit CloseReport activity + transition RM → CLOSED
- ``CloseCase``        — Case Owner guard + PreCloseAction hook +
                         guard (not already closed) + emit CloseReport + RM → CLOSED

Trees are run via ``BTBridge.execute_with_setup()`` in the corresponding
trigger use case.

Per issue #849 AC-1 through AC-3 and specs/behavior-tree-integration.yaml
BT-15-001, BT-15-002.
Per issue #1854 AC-1 through AC-5: CheckCaseOwner guard, PreCloseAction
call-out point, and rename to ``create_close_case_trigger_tree`` /
``SvcCloseCaseUseCase``.
"""

import logging
from typing import TYPE_CHECKING

import py_trees

from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckIsCaseOwnerNode,
)
from vultron.core.behaviors.report.nodes.conditions import CheckReportNotClosed
from vultron.core.behaviors.report.nodes.emit import (
    EmitCloseReportActivity,
    EmitInvalidateReportActivity,
    EmitSubmitReportActivity,
)
from vultron.core.behaviors.report.nodes.rm_transitions import (
    TransitionRMtoClosed,
    TransitionRMtoInvalid,
)

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.close_report import (
        CloseReportCallOutBundle,
    )

logger = logging.getLogger(__name__)


def create_invalidate_report_trigger_tree(
    offer_id: str,
    report_id: str,
    captured: dict | None = None,
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
        captured: Optional dict; ``captured["activity"]`` is set to the
            serialised activity dict on success (DL-06-001, AC-1).

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
                captured=captured,
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


def create_close_case_trigger_tree(
    actor_id: str,
    case_id: str,
    offer_id: str,
    report_id: str,
    result_out: dict,
    captured: dict | None = None,
    call_out: "CloseReportCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the close-case trigger workflow.

    Guards that only the Case Owner may close the case, runs the
    ``PreCloseAction`` Actuator call-out hook, guards against
    duplicate-close, emits ``RmCloseReportActivity``, and records the
    actor's RM state as CLOSED.

    On a duplicate-close attempt ``CheckReportNotClosed`` writes a
    :class:`~vultron.errors.VultronInvalidStateTransitionError` into
    ``result_out["error"]`` so the calling use case can re-raise the domain
    exception.

    Structure::

        CloseCaseTriggerBT (Sequence)
        ├─ CheckCaseOwner           # guard: FAILURE if actor is not CASE_OWNER
        ├─ CheckReportNotClosed     # guard: FAILURE + error if already CLOSED
        ├─ PreCloseAction           # Actuator call-out; default = AlwaysSucceed
        ├─ EmitCloseReportActivity  # emit activity + queue in outbox
        └─ TransitionRMtoClosed     # persist report-phase RM.CLOSED

    Per issue #849 AC-3: the duplicate-close guard is a BT condition node, not
    a procedural ``raise`` in ``execute()``.
    Per issue #1854 AC-1/AC-2: CheckCaseOwner guard and PreCloseAction wired.

    Args:
        actor_id: ID of the actor attempting to close the case.
        case_id: ID of the VulnerabilityCase to close.
        offer_id: ID of the Offer being closed.
        report_id: ID of the VulnerabilityReport.
        result_out: Mutable dict for surfacing domain errors back to the caller.
            ``result_out["error"]`` is set to a
            ``VultronInvalidStateTransitionError`` when the report is already
            closed.
        captured: Optional dict; ``captured["activity"]`` is set to the
            serialised activity dict on success (DL-06-001, AC-1).
        call_out: Optional :class:`~vultron.core.behaviors.call_out.bundles
            .close_report.CloseReportCallOutBundle` supplying a custom
            ``pre_close_action_factory``.  Defaults to
            :data:`~vultron.core.behaviors.call_out.bundles.close_report
            .CLOSE_REPORT_DETERMINISTIC` (``AlwaysSucceed``).

    Returns:
        Root node of the ``CloseCaseTriggerBT`` Sequence.
    """
    from vultron.core.behaviors.call_out.bundles.close_report import (
        CLOSE_REPORT_DETERMINISTIC,
    )

    bundle = call_out if call_out is not None else CLOSE_REPORT_DETERMINISTIC
    pre_close_node = bundle.pre_close_action_factory("PreCloseAction")

    root = py_trees.composites.Sequence(
        name="CloseCaseTriggerBT",
        memory=False,
        children=[
            CheckIsCaseOwnerNode(
                sender_actor_id=actor_id,
                case_id=case_id,
                name="CheckCaseOwner",
            ),
            CheckReportNotClosed(
                report_id=report_id,
                result_out=result_out,
            ),
            pre_close_node,
            EmitCloseReportActivity(
                offer_id=offer_id,
                report_id=report_id,
                captured=captured,
            ),
            TransitionRMtoClosed(
                report_id=report_id,
                offer_id=offer_id,
            ),
        ],
    )
    logger.debug(
        "Created CloseCaseTriggerBT for case=%s offer=%s report=%s",
        case_id,
        offer_id,
        report_id,
    )
    return root


def create_close_report_trigger_tree(
    offer_id: str,
    report_id: str,
    result_out: dict,
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Deprecated alias for :func:`create_close_case_trigger_tree`.

    .. deprecated::
        Use :func:`create_close_case_trigger_tree` directly.  This shim
        exists only for callers that have not yet been updated; it omits the
        ``actor_id`` / ``case_id`` / ``call_out`` parameters and therefore
        bypasses the ``CheckCaseOwner`` guard and ``PreCloseAction`` hook.

    Returns:
        Root node of the ``CloseReportTriggerBT`` Sequence (legacy structure).
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
                captured=captured,
            ),
            TransitionRMtoClosed(
                report_id=report_id,
                offer_id=offer_id,
            ),
        ],
    )
    logger.debug(
        "Created CloseReportTriggerBT (legacy) for offer=%s report=%s",
        offer_id,
        report_id,
    )
    return root


def submit_report_trigger_bt(
    report_id: str,
    recipient_id: str,
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the submit-report trigger workflow.

    Emits ``Offer(VulnerabilityReport)`` addressed to *recipient_id* and
    queues the offer ID in the actor's outbox.

    Structure::

        SubmitReportTriggerBT (Sequence)
        └─ EmitSubmitReportActivity  # emit offer + queue in outbox

    Args:
        report_id: ID of the already-persisted VulnerabilityReport.
        recipient_id: Actor URI to send the offer to.
        captured: Optional dict; ``captured["offer"]`` is set to the
            serialised offer dict on success.

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
            ),
        ],
    )
    logger.debug(
        "Created SubmitReportTriggerBT for report=%s recipient=%s",
        report_id,
        recipient_id,
    )
    return root
