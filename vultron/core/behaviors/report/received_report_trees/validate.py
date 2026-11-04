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

"""Received-side BT for ``ValidateReport``: the sender's RM → VALID.

The RM write is about the sender, never the receiving actor (RSH-08-001), and
is adjudicated by the shared received-side RM acceptance rule (RSH-06-006).
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.participant.status_entries import (
    CommitParticipantStatusEntriesNode,
)
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.report.rm_declaration_tree import (
    rm_declaration_guard,
    rm_gap_note,
)
from vultron.core.behaviors.report.validate_tree import (
    create_validate_report_subtree,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    SenderCheckContext,
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

    Composes the validate-report workflow for a received
    ``Accept(Offer(VulnerabilityReport))`` activity: the sender declares that
    *its* RM state is ``VALID``.  All nodes that need the sender's identity
    receive ``sender_actor_id`` as an explicit constructor arg so the tree can
    run under ``actor_id=receiving_actor_id`` while the RM write is about the
    *sender* (RSH-08-001, BT-17-006).

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
        ├── RecordRMValidStatus                     # status entry, CLP-07-013
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
            composes the sender guard from it (HP-01-025).

    Returns:
        Root node of the ``ValidateReportReceivedBT`` Sequence.
    """
    written: list[str] = []
    validation = create_validate_report_subtree(
        report_id=report_id,
        offer_id=offer_id,
        sender_actor_id=sender_actor_id,
        emit=False,
        rm_rule=RMRule.DECLARATION,
        written_ids=written,
    )

    # RSH-08-003: the sender's RM → VALID is canonical participant state only
    # the CASE_MANAGER writes; ``validate_report`` is committed, then the
    # status it wrote follows as its own entry, which a replica copies from
    # the ledger fan-out, not from the direct Accept (#3814, CLP-07-013).  With no case
    # (``case_id`` None) the sender guard refuses the activity before any
    # effect, so there is nothing to gate.
    manager_effects = (
        [
            validation,
            # The status the validation wrote, as its own entry (CLP-07-013).
            CommitParticipantStatusEntriesNode(
                subject_actor_id=sender_actor_id,
                case_id=case_id,
                status_ids=written,
                name="RecordRMValidStatus",
            ),
            rm_gap_note(sender_actor_id, case_id),
        ]
        if case_id is not None
        else None
    )
    root = create_receive_activity_tree(
        name="ValidateReportReceivedBT",
        case_id=case_id,
        # The participant declares RM.VALID to the CASE_MANAGER, which
        # adjudicates and commits it; a participant replica that holds a copy
        # archives it and takes the sender's RM state from the ledger entry
        # that follows the act, never from the declaration itself
        # (RSH-06-006, RSH-08-003, HP-01-038).
        paths={ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA},
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
