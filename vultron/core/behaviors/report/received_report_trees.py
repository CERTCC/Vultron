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
inbound protocol handling (intake archives each received activity first,
CLP-10-017) for one of the four report-lifecycle activities:

- ``CreateReport`` — store VulnerabilityReport
- ``AckReport``    — forward the acknowledgement
- ``CloseReport``  — record the *sender's* RM → CLOSED
- ``InvalidateReport`` — record the *sender's* RM → INVALID

with ``ValidateReport`` (the sender's RM → VALID) alongside.  Every RM write
here is about the sender of the activity, never the receiving actor whose store
the tree runs in (RSH-08-001), and is adjudicated by the received-side RM
acceptance rule shared with ``Add(ParticipantStatus)`` (RSH-06-006) — see
:mod:`vultron.core.behaviors.report.rm_declaration_tree`.

Trees are run via ``BTBridge.execute_with_setup()`` in the corresponding use
case.

Per issue #759 AC-1 through AC-4.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.case_lookup import RequireCaseForReport
from vultron.core.behaviors.case.nodes.conditions import (
    CheckIsCaseManagerNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.report.nodes.emit import EmitAckReportActivity
from vultron.core.behaviors.report.nodes.storage import (
    StoreReportNode,
)
from vultron.core.behaviors.report.rm_declaration_tree import (
    record_rm_declaration,
    rm_declaration_guard,
    rm_gap_note,
)
from vultron.core.behaviors.report.validate_tree import (
    create_validate_report_subtree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderIsActiveParticipantNode,
    SenderIsExecutingActorNode,
)
from vultron.core.models.events.report import (
    AckReportReceivedEvent,
    CloseReportReceivedEvent,
    CreateReportReceivedEvent,
    InvalidateReportReceivedEvent,
)
from vultron.core.states.rm import RM, RMRule

logger = logging.getLogger(__name__)


def create_validate_report_received_tree(
    report_id: str,
    offer_id: str,
    sender_actor_id: str,
    case_id: str | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the single-BT received-side tree for ValidateReport (ADR-0022).

    Composes the validate-report workflow for a received ``Accept(Offer(Report))``
    activity: the sender declares that *its* RM state is ``VALID``.  All nodes
    that need the sender's identity receive ``sender_actor_id`` as an explicit
    constructor arg so the tree can run under ``actor_id=receiving_actor_id``
    while the RM write is about the *sender* (RSH-08-001, BT-17-006).

    The sender must be a participant of the case (HP-01-006), and the
    declaration is adjudicated under the received-side RM acceptance rule
    before the commit (RSH-06-006, CLP-10-006): a backward move is refused, a
    non-adjacent forward one is recorded and flagged for the RSH-06-004 note.

    When ``case_id`` is provided, a guarded-commit subtree is inserted before
    the validation effects so receipt is recorded before any RM state
    transitions run (CLP-10-006).  Pass ``None`` to skip ledger commit.

    The validation subtree itself is built by
    :func:`~vultron.core.behaviors.report.validate_tree.create_validate_report_subtree`
    with ``emit=False`` — one definition shared with the trigger side
    (ARCH-15-004).  ``emit=False`` because the activity being handled *is* the
    ``validate-report`` message; re-emitting it would loop.  It records the
    participant write with ``rm_rule=RMRule.DECLARATION`` so the move the guard
    accepted is not refused at the write.

    Structure::

        ValidateReportReceivedBT (Sequence)
        ├── Intake
        ├── SenderIsActiveParticipantNode           # HP-01-006
        ├── AdjudicateRMDeclarationNode(VALID)      # RSH-06-006
        ├── GuardedCommitCaseLedgerEntryBT (only if case_id)  # CLP-10-006
        ├── ValidateReportBT (Selector)
        │   ├── CheckRMStateValid(sender_actor_id)      # idempotency exit
        │   └── ValidationFlow (Sequence)
        │       ├── CheckRMStateReceivedOrInvalid(sender_actor_id)
        │       ├── EvaluateReportCredibility
        │       ├── EvaluateReportValidity
        │       ├── RequireCaseForReport                # publishes /case_id
        │       ├── EnsureEmbargoExists                 # DUR-07-004
        │       └── ValidationActions (Sequence)
        │           └── TransitionRMtoValid(sender_actor_id)
        └── EmitRMGapNoteNode                       # RSH-06-004

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
        rm_rule=RMRule.DECLARATION,
    )

    root = create_receive_activity_tree(
        name="ValidateReportReceivedBT",
        case_id=case_id,
        precondition_guards=[
            SenderIsActiveParticipantNode(
                status_id="",
                sender_actor_id=sender_actor_id,
                case_id=case_id,
            ),
            rm_declaration_guard(sender_actor_id, RM.VALID, case_id),
        ],
        effect_nodes=[validation, rm_gap_note(sender_actor_id, case_id)],
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

    Steps (Sequence via :func:`create_receive_activity_tree`):
    1. Intake archives the ``Create`` as received (CLP-10-017), so a refused
       delivery still leaves its record (CLP-10-018).
    2. Store VulnerabilityReport idempotently.

    No ledger commit: the tree carries no case context (``case_id=None``).

    Args:
        request: The parsed inbound domain event.

    Returns:
        Root node of the ``CreateReportReceivedBT`` Sequence.
    """
    report_id = request.report_id or ""
    activity_id = request.activity_id or ""

    root = create_receive_activity_tree(
        name="CreateReportReceivedBT",
        case_id=None,
        precondition_guards=[],
        effect_nodes=[
            StoreReportNode(
                report_id=report_id,
                report_obj=request.report,
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

    1. Intake archives the ``Read`` as received (CLP-10-017); the per-tree
       ``StoreActivityNode`` it once carried duplicated intake and was
       removed (CLP-10-019).
    2. Guarded commit (only when ``case_id`` is provided and the receiving
       actor holds ``CVDRole.CASE_MANAGER``) — records receipt before any
       effects run (CLP-10-006).
    3. Forward the ack to the CASE_MANAGER — only when it is the executing
       actor's *own* ack and that actor is not itself the CASE_MANAGER.

    Step 3 serves the own-inbox pattern: an actor that acknowledges a report
    by posting the ``Read`` to its own inbox relies on this tree to forward
    it.  The received side *does* carry a TriggerActivityPort
    (``ACK_REPORT`` is wired for it), so ``EmitAckReportActivity`` really
    emits, authored as the blackboard ``actor_id``.  Hence the two skips:

    - another actor's ack must not be re-emitted under this actor's name;
    - the CASE_MANAGER has just committed the ack, and a forward would be
      addressed to itself and loop back through HTTP delivery to its own
      inbox (OX-12-001) under a fresh id, forever (#2667).

    ``NoEmitFallback`` still absorbs an emit failure (no routable recipient,
    or no port in a caller that did not wire one).

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
            py_trees.decorators.Inverter(
                name="SkipIfAckFromAnotherActor",
                child=SenderIsExecutingActorNode(
                    sender_actor_id=request.actor_id
                ),
            ),
            CheckIsCaseManagerNode(case_id=case_id, name="SkipIfCaseManager"),
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
        effect_nodes=[maybe_emit],
    )
    logger.debug(
        "Created AckReportReceivedBT for activity=%s case=%s",
        activity_id,
        case_id,
    )
    return root


def _create_report_verdict_received_tree(
    request: CloseReportReceivedEvent | InvalidateReportReceivedEvent,
    case_id: str | None,
    declared_rm: RM,
    name: str,
    write_name: str,
) -> py_trees.behaviour.Behaviour:
    """Compose the received tree for a report verdict that declares *declared_rm*.

    Shared by the report-closed and report-invalid handlers, which differ only
    in the RM state their activity declares for its sender.

    The subject of the RM write is the sender, ``request.actor_id``; the tree
    still executes in the receiving actor's store (RSH-08-001, BT-17-006).
    """
    sender_actor_id = request.actor_id
    root = create_receive_activity_tree(
        name=name,
        # No ledger commit: these verdicts have never been committed, and
        # their ledger replay is #3814's to add (RSH-08-004).
        case_id=None,
        precondition_guards=[
            RequireCaseForReport(report_id=request.report_id),
            # The sender is checked against the case, so the case is resolved
            # first: an activity about a case this store does not hold is
            # refused as such (#2255), not as an unknown sender.
            SenderIsActiveParticipantNode(
                status_id="",
                sender_actor_id=sender_actor_id,
                case_id=case_id,
            ),
            rm_declaration_guard(sender_actor_id, declared_rm, case_id),
        ],
        effect_nodes=record_rm_declaration(
            sender_actor_id, declared_rm, case_id, name=write_name
        ),
    )
    logger.debug(
        "Created %s for report=%s activity=%s sender=%s case=%s",
        name,
        request.report_id,
        request.activity_id,
        sender_actor_id,
        case_id,
    )
    return root


def create_close_report_received_tree(
    request: CloseReportReceivedEvent,
    case_id: str | None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the CloseReportReceived workflow.

    Handles receipt of a ``Reject(Offer(VulnerabilityReport))`` (CloseReport)
    activity: the sender declares that *its* RM state is ``CLOSED``.  The
    subject of the write is therefore the sender (``request.actor_id``), never
    the receiving actor whose store the tree runs in (RSH-08-001, HP-00-001).

    Steps (Sequence via :func:`create_receive_activity_tree`):
    1. Intake archives the ``Reject`` as received (CLP-10-017); the activity
       stays archived when a later step refuses (CLP-10-018).
    2. Resolve this actor's case for the report (``RequireCaseForReport``,
       which also publishes ``/case_id`` for downstream nodes).
    3. The sender must be a participant of that case (HP-01-006).
    4. Adjudicate the declaration under the received-side RM rule: a backward
       move is refused here, before any effect (RSH-06-002, CLP-10-009).
    5. Record ``CLOSED`` for the sender unless it is already recorded
       (RSH-08-002), through the canonical
       :class:`~vultron.core.behaviors.case.nodes.participant.status\
.CreateParticipantStatusNode` writer (ADR-0089).
    6. Post the RSH-06-004 clarification note when step 4 saw a
       non-adjacent jump.

    Steps 2–4 return FAILURE when the case is not in this actor's store, so the
    handler reports a refusal of an activity about an unknown case (#2255,
    ARCH-15-001, ISSUE-2548); the activity archived in step 1 still records
    that it arrived.

    Args:
        request: The parsed inbound domain event.  Its ``actor_id`` — the
            sender — is the subject of the RM write.
        case_id: The receiving store's case for the report, resolved by the
            use case before the tree runs; ``None`` when it holds none.

    Returns:
        Root node of the ``CloseReportReceivedBT`` Sequence.
    """
    return _create_report_verdict_received_tree(
        request,
        case_id,
        declared_rm=RM.CLOSED,
        name="CloseReportReceivedBT",
        write_name="TransitionRMtoClosed",
    )


def create_invalidate_report_received_tree(
    request: InvalidateReportReceivedEvent,
    case_id: str | None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the InvalidateReportReceived workflow.

    Handles receipt of a ``TentativeReject(Offer(VulnerabilityReport))``
    (InvalidateReport) activity: the sender declares that *its* RM state is
    ``INVALID``.  The subject of the write is the sender
    (``request.actor_id``), never the receiving actor (RSH-08-001).

    The steps are those of :func:`create_close_report_received_tree`, with
    ``INVALID`` as the declared state.

    Args:
        request: The parsed inbound domain event.  Its ``actor_id`` — the
            sender — is the subject of the RM write.
        case_id: The receiving store's case for the report, resolved by the
            use case before the tree runs; ``None`` when it holds none.

    Returns:
        Root node of the ``InvalidateReportReceivedBT`` Sequence.
    """
    return _create_report_verdict_received_tree(
        request,
        case_id,
        declared_rm=RM.INVALID,
        name="InvalidateReportReceivedBT",
        write_name="TransitionRMtoInvalid",
    )
