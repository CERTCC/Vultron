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
CLP-10-017) for one of the report-lifecycle activities:

- ``CreateReport`` — store VulnerabilityReport
- ``AckReport``    — check the acknowledgement's sender
- ``InvalidateReport`` — record the *sender's* RM → INVALID

with ``ValidateReport`` (the sender's RM → VALID) alongside, and
``CloseReport``, which no receiver applies: its tree only refuses it
(CM-23-019).
Every RM write
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
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
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
    SenderIsParticipantNode,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import (
    ReportOfferRequest,
    SenderCheckContext,
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
    *,
    sender_rule: SenderRule,
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
    transitions run (CLP-10-006).  With ``None`` the sender guard has no case
    to check the sender against, so the tree refuses the activity.

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
        ├── SenderIsParticipantNode                 # HP-01-006
        ├── AdjudicateRMDeclarationNode(VALID)      # RSH-06-006
        ├── GuardedCommitCaseLedgerEntryBT          # CLP-10-006
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

    ``AdjudicateRMDeclarationNode`` sits in the factory's
    ``PreconditionGuardStage``: when it refuses a regression, the
    refusal-effects stage posts the same RSH-06-004 note before the tree
    fails (CLP-10-022).

    There is no ``Success("ValidationSkipped")`` mask around the validation
    subtree any more.  It turned every validation failure into a SUCCESS the
    caller could not distinguish from a real one (ARCH-15-001) — including the
    ISSUE-2548 case where the sender's case replica had not arrived yet.

    Args:
        report_id: ID of the VulnerabilityReport being validated.
        offer_id: ID of the Offer activity that carried the report.
        sender_actor_id: Actor ID of the message sender (the validating actor).
            Used by validation nodes instead of the blackboard ``actor_id``.
        case_id: ID of the VulnerabilityCase linked to this report, which
            the sender guard, the RM adjudication and the guarded commit
            read; ``None`` when this store holds no case for the report.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-008).

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

    # RSH-08-003: the sender's RM → VALID is canonical participant state only
    # the CASE_MANAGER writes; ``validate_report`` is committed and replayed
    # onto the sender's participant (RmVerdict slot), so a replica takes it from
    # the ledger fan-out, not from the direct Accept (#3814).  With no case
    # (``case_id`` None) the sender guard refuses the activity before any
    # effect, so there is nothing to gate.
    manager_effects = (
        [validation, rm_gap_note(sender_actor_id, case_id)]
        if case_id is not None
        else None
    )
    root = create_receive_activity_tree(
        name="ValidateReportReceivedBT",
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_actor_id, case_id=case_id
        ),
        precondition_guards=[
            rm_declaration_guard(sender_actor_id, RM.VALID, case_id),
        ],
        manager_effects=manager_effects,
        manager_case_id=case_id if manager_effects else None,
        manager_gate_name=(
            "ValidateReportEffectsIfCaseManager" if manager_effects else None
        ),
        refusal_effects=[rm_gap_note(sender_actor_id, case_id)],
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
        replica_effects=[
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
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the AckReportReceived workflow.

    Handles receipt of a ``Read(Offer(Report))`` (AckReport, RK).  RK goes
    from an actor the ``Offer(VulnerabilityReport)`` was addressed to, to the
    reporter, and never to the CASE_MANAGER (RMB-08-003), so the tree has no
    case context, no ledger commit and nothing to emit.

    Steps (Sequence via :func:`create_receive_activity_tree`):

    1. Intake archives the ``Read`` as received (CLP-10-017), so a refused
       acknowledgement still leaves its record (CLP-10-018).
    2. The sender guard the factory composes from *sender_rule* refuses a
       sender that is not an addressee of the Offer this store recorded
       (``SenderIsOfferAddresseeNode``; RMB-08-004, HP-01-006).

    An acknowledgement changes no state (RMB-08-001), so an admitted RK
    writes nothing past intake.

    Args:
        request: The parsed inbound domain event.
        sender_rule: The use case's declared sender rule (HP-01-008).

    Returns:
        Root node of the ``AckReportReceivedBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="AckReportReceivedBT",
        case_id=None,
        precondition_guards=[],
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=request.actor_id,
            request=ReportOfferRequest(offer_id=request.offer_id),
        ),
    )
    logger.debug(
        "Created AckReportReceivedBT for activity=%s offer=%s",
        request.activity_id,
        request.offer_id,
    )
    return root


def _report_verdict_stages(
    request: InvalidateReportReceivedEvent,
    case_id: str | None,
    declared_rm: RM,
    write_name: str,
) -> tuple[
    list[py_trees.behaviour.Behaviour],
    list[py_trees.behaviour.Behaviour],
    list[py_trees.behaviour.Behaviour],
]:
    """Return the guards, effects and refusal effects of a report verdict.

    The verdict declares *declared_rm* for the sender; the refusal effect is
    the RSH-06-004 note owed when the guard refuses a regression
    (CLP-10-022).

    The report-invalid factory composes them through
    :func:`create_receive_activity_tree` itself (CLP-10-017).  A
    ``Close(Report)`` has no verdict to stage: its tree refuses it
    (CM-23-019).

    The subject of the RM write is the sender, ``request.actor_id``; the tree
    still executes in the receiving actor's store (RSH-08-001, BT-17-006).
    """
    sender_actor_id = request.actor_id
    guards: list[py_trees.behaviour.Behaviour] = [
        RequireCaseForReport(report_id=request.report_id),
        # The sender is checked against the case, so the case is resolved
        # first: an activity about a case this store does not hold is refused
        # as such (#2255), not as an unknown sender.
        SenderIsParticipantNode(
            sender_actor_id=sender_actor_id,
            case_id=case_id,
        ),
        rm_declaration_guard(sender_actor_id, declared_rm, case_id),
    ]
    effects = record_rm_declaration(
        sender_actor_id, declared_rm, case_id, name=write_name
    )
    logger.debug(
        "Building %s received tree for report=%s activity=%s sender=%s case=%s",
        declared_rm,
        request.report_id,
        request.activity_id,
        sender_actor_id,
        case_id,
    )
    return guards, effects, [rm_gap_note(sender_actor_id, case_id)]


def create_close_report_received_tree(
    request: CloseReportReceivedEvent,
    case_id: str | None,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the CloseReportReceived workflow (CM-23-019).

    Handles receipt of a ``Reject(Offer(VulnerabilityReport))``
    (CloseReport).  No receiver applies one, so the tree has no effect, and
    its commit stage is never reached; it only decides how the activity is
    refused:

    1. Intake archives the ``Reject`` as received (CLP-10-017, CLP-10-018).
    2. The post-close guard drops it on a fully closed case (CM-23-013).
    3. The sender guard is composed from the use case's declared rule
       (HP-01-008).  On a case that holds the report the rule admits no
       sender on either side, so every sender is refused with nothing
       written or sent: the Case Owner closes a case by
       ``Leave(VulnerabilityCase)``, and nobody else holds the report.
       Before any case exists the rule's outside-case side checks the
       sender is an addressee of the Offer it closes.
    4. ``RequireCaseForReport`` then refuses a report this store holds no
       case for, as an activity about an unknown case (#2255).

    Args:
        request: The parsed inbound domain event.
        case_id: The receiving store's case for the report, resolved by the
            use case before the tree runs; ``None`` when it holds none.
        sender_rule: The use case's declared sender rule (HP-01-008).

    Returns:
        Root node of the ``CloseReportReceivedBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="CloseReportReceivedBT",
        # The case names the sender guard's side and the post-close boundary;
        # the guard admits no sender on a case, so the commit never runs.
        case_id=case_id,
        precondition_guards=[
            RequireCaseForReport(report_id=request.report_id)
        ],
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=request.actor_id,
            case_id=case_id,
            request=ReportOfferRequest(offer_id=request.offer_id),
        ),
    )
    logger.debug(
        "Created CloseReportReceivedBT for report=%s activity=%s case=%s",
        request.report_id,
        request.activity_id,
        case_id,
    )
    return root


def create_invalidate_report_received_tree(
    request: InvalidateReportReceivedEvent,
    case_id: str | None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the InvalidateReportReceived workflow.

    Handles receipt of a ``TentativeReject(Offer(VulnerabilityReport))``
    (InvalidateReport) activity: the sender declares that *its* RM state is
    ``INVALID``.  The subject of the write is the sender
    (``request.actor_id``), never the receiving actor (RSH-08-001).

    Steps (Sequence via :func:`create_receive_activity_tree`):
    1. Intake archives the ``TentativeReject`` as received (CLP-10-017); the
       activity stays archived when a later step refuses (CLP-10-018).
    2. Resolve this actor's case for the report (``RequireCaseForReport``,
       which also publishes ``/case_id`` for downstream nodes).
    3. The sender must be a participant of that case (HP-01-006).
    4. Adjudicate the declaration under the received-side RM rule: a backward
       move is refused here, before any effect (RSH-06-002, CLP-10-009).
    5. Guarded commit (only when ``case_id`` is provided and the receiving
       actor holds ``CVDRole.CASE_MANAGER``) records the activity after the
       guards and before the effect (CLP-10-006, CLP-10-013):
       ``("TentativeReject", "Offer")`` is a canonical signature.
    6. Record ``INVALID`` for the sender unless it is already recorded
       (RSH-08-002), through the canonical
       :class:`~vultron.core.behaviors.case.nodes.participant.status\
.CreateParticipantStatusNode` writer (ADR-0089).
    7. Post the RSH-06-004 clarification note when step 4 saw a
       non-adjacent jump.  When step 4 refuses a regression, the factory's
       refusal-effects stage posts the note instead, at the CASE_MANAGER,
       and the tree still fails before any effect (CLP-10-022).

    Steps 2–4 return FAILURE when the case is not in this actor's store, so
    the handler reports a refusal of an activity about an unknown case
    (#2255, ARCH-15-001, ISSUE-2548).

    Args:
        request: The parsed inbound domain event.  Its ``actor_id`` — the
            sender — is the subject of the RM write.
        case_id: The receiving store's case for the report, resolved by the
            use case before the tree runs; ``None`` when it holds none.

    Returns:
        Root node of the ``InvalidateReportReceivedBT`` Sequence.
    """
    guards, effects, refusal = _report_verdict_stages(
        request,
        case_id,
        declared_rm=RM.INVALID,
        write_name="TransitionRMtoInvalid",
    )
    return create_receive_activity_tree(
        name="InvalidateReportReceivedBT",
        # A canonical signature: the CASE_MANAGER commits it after the guards,
        # and replicas replay it (CLP-10-013, RSH-08-004).  RSH-08-003: the
        # sender's RM → INVALID is committed and replayed (RmVerdict slot), so a
        # replica takes it from the ledger, not from the direct TentativeReject
        # (#3814).  With no case the guards refuse before any effect.
        case_id=case_id,
        precondition_guards=guards,
        manager_effects=effects if case_id is not None else None,
        manager_case_id=case_id if case_id is not None else None,
        manager_gate_name=(
            "InvalidateReportEffectsIfCaseManager"
            if case_id is not None
            else None
        ),
        refusal_effects=refusal,
    )
