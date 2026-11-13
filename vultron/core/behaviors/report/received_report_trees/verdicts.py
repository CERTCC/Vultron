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

"""Received-side BTs for the ``CloseReport`` and ``InvalidateReport`` verdicts.

``InvalidateReport`` records the *sender's* RM → INVALID (RSH-08-001,
RSH-06-006); ``CloseReport`` is applied by no receiver, so its tree only
refuses it (CM-23-019).
"""

import logging
from typing import NamedTuple

import py_trees

from vultron.core.behaviors.case.nodes.case_lookup import RequireCaseForReport
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.report.rm_declaration_tree import (
    record_rm_declaration,
    rm_declaration_guard,
    rm_gap_note,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    ReportOfferRequest,
    SenderCheckContext,
)
from vultron.core.models.events.report import (
    CloseReportReceivedEvent,
    InvalidateReportReceivedEvent,
)
from vultron.core.states.rm import RM

logger = logging.getLogger(__name__)


class _ReportVerdictStages(NamedTuple):
    """The stages of a report verdict's received tree."""

    case_resolution: list[py_trees.behaviour.Behaviour]
    sender_context: SenderCheckContext
    guards: list[py_trees.behaviour.Behaviour]
    effects: list[py_trees.behaviour.Behaviour]
    refusal: list[py_trees.behaviour.Behaviour]


def _report_verdict_stages(
    request: InvalidateReportReceivedEvent,
    case_id: str | None,
    declared_rm: RM,
    write_name: str,
) -> _ReportVerdictStages:
    """Return the stages of a report verdict.

    The verdict declares *declared_rm* for the sender; the refusal effect is
    the RSH-06-004 note owed when the guard refuses a regression
    (CLP-10-022).

    The case is resolved first, so the sender is checked against it only
    once it is known: an activity about a case this store does not hold is
    refused as such (#2255), not as an unknown sender.

    The report-invalid factory composes them through
    :func:`create_receive_activity_tree` itself (CLP-10-017).  A
    ``Reject(Offer(VulnerabilityReport))`` has no verdict to stage: its tree
    refuses it (CM-23-019).

    The subject of the RM write is the sender, ``request.actor_id``; the tree
    still executes in the receiving actor's store (RSH-08-001, BT-17-006).
    """
    sender_actor_id = request.actor_id
    logger.debug(
        "Building %s received tree for report=%s activity=%s sender=%s case=%s",
        declared_rm,
        request.report_id,
        request.activity_id,
        sender_actor_id,
        case_id,
    )
    return _ReportVerdictStages(
        case_resolution=[RequireCaseForReport(report_id=request.report_id)],
        sender_context=SenderCheckContext(
            sender_id=sender_actor_id, case_id=case_id
        ),
        guards=[rm_declaration_guard(sender_actor_id, declared_rm, case_id)],
        effects=record_rm_declaration(
            sender_actor_id, declared_rm, case_id, name=write_name
        ),
        refusal=[rm_gap_note(sender_actor_id, case_id)],
    )


def create_close_report_received_tree(
    request: CloseReportReceivedEvent,
    case_id: str | None,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the CloseReportReceived workflow (CM-23-019).

    Handles receipt of a ``Reject(Offer(VulnerabilityReport))``
    (CloseReport).  No receiver applies one, so the tree has no effect, and
    its commit stage is never reached; it only decides how the activity is
    refused:

    1. The post-close door drops it on a fully closed case (CM-23-013).
    2. The path stage refuses a receiver that holds the report's case: the
       type declares the no-case path alone, so every sender is refused there
       with nothing written or sent (the Case Owner closes a case by
       ``Leave(VulnerabilityCase)``, and nobody else holds the report).  On
       the no-case path the sender guard, a door composed from the use
       case's declared rule (HP-01-025, HP-01-036), checks the rule's
       outside-case side: the sender is an addressee of the Offer it closes.
       A door refusal leaves only a receipt stub (CLP-10-018).
    3. Intake records the admitted ``Reject`` as received (CLP-10-017).
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
        # The case names the post-close boundary; the path stage picks the
        # sender guard's side, and on the one declared path it is the
        # outside-case side (HP-01-036), so the commit never runs on a case.
        case_id=case_id,
        # No receiver applies a CloseReport: the rule admits a sender only
        # before any case exists, so that is the one path the type handles
        # and a receiver holding the case is refused at the stage
        # (CM-23-019, HP-01-038, HP-01-039).
        paths={ReceivedPath.NO_CASE},
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
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the InvalidateReportReceived workflow.

    Handles receipt of a ``TentativeReject(Offer(VulnerabilityReport))``
    (InvalidateReport) activity: the sender declares that *its* RM state is
    ``INVALID``.  The subject of the write is the sender
    (``request.actor_id``), never the receiving actor (RSH-08-001).

    Steps (Sequence via :func:`create_receive_activity_tree`):
    1. Resolve this actor's case for the report (``RequireCaseForReport``,
       which also publishes ``/case_id`` for downstream nodes).
    2. The sender must be a participant of that case (HP-01-006).
    3. Once those doors admit it, intake records the ``TentativeReject`` as
       received (CLP-10-017); a refusal by a door or a later step leaves a
       receipt stub (CLP-10-018).
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

    Steps 1, 2 and 4 return FAILURE when the case is not in this actor's
    store, so the handler reports a refusal of an activity about an unknown
    case (#2255, ARCH-15-001, ISSUE-2548).

    Args:
        request: The parsed inbound domain event.  Its ``actor_id`` — the
            sender — is the subject of the RM write.
        case_id: The receiving store's case for the report, resolved by the
            use case before the tree runs; ``None`` when it holds none.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it after the case is resolved
            (HP-01-025).

    Returns:
        Root node of the ``InvalidateReportReceivedBT`` Sequence.
    """
    stages = _report_verdict_stages(
        request,
        case_id,
        declared_rm=RM.INVALID,
        write_name="TransitionRMtoInvalid",
    )
    return create_receive_activity_tree(
        name="InvalidateReportReceivedBT",
        # The participant declares RM.INVALID to the CASE_MANAGER, which
        # adjudicates and commits it; a participant replica archives its copy
        # and takes the RM state from the ledger entry that follows
        # (RSH-06-006, RSH-08-003, HP-01-038).  With no case at build time
        # the receiver holds none for the report, so it is on the no-case
        # path, whose empty side admits no sender; ``case_resolution``
        # refuses the delivery as about an unknown case before that side is
        # read (#2255, HP-01-036).  A report-scoped verdict reaches the tree
        # without its case being known, so the declaration is the one
        # HP-01-041 admits.
        paths=(
            {ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA}
            if case_id is not None
            else {ReceivedPath.NO_CASE}
        ),
        # A canonical signature: the CASE_MANAGER commits it after the guards,
        # and replicas replay it (CLP-10-013, RSH-08-004).  RSH-08-003: the
        # sender's RM → INVALID is committed as the status entry that follows
        # the act, so a replica copies it from the ledger, not from the direct
        # TentativeReject (#3814, CLP-07-013).  With no case the guards refuse
        # before any effect.
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=stages.sender_context,
        case_resolution=stages.case_resolution,
        precondition_guards=stages.guards,
        manager_effects=stages.effects if case_id is not None else None,
        manager_case_id=case_id if case_id is not None else None,
        manager_gate_name=(
            "InvalidateReportEffectsIfCaseManager"
            if case_id is not None
            else None
        ),
        refusal_effects=stages.refusal,
    )
