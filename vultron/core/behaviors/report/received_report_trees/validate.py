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

from vultron.core.behaviors.act_key_scope import with_act_keys
from vultron.core.behaviors.act_keys import REPORT_ID, SENDER_ID
from vultron.core.behaviors.case.nodes.case_lookup import FindCaseForReport
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
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the single-BT received-side tree for ValidateReport (ADR-0022).

    Composes the validate-report workflow for a received
    ``Accept(Offer(VulnerabilityReport))`` activity: the sender declares that
    *its* RM state is ``VALID``.  All nodes that need the sender's identity
    read it from ``sender_actor_id`` or ``/sender_id``, so the tree can run
    under ``actor_id=receiving_actor_id`` while the RM write is about the
    *sender* (RSH-08-001, BT-17-006).

    The tree finds its case itself: :class:`FindCaseForReport` runs ahead
    of the path stage and publishes the report's case on ``/case_id``, the
    one source of that key in the tree (BT-25-009, BT-25-011), so the use
    case reads no store (ADR-0195).  A receiver that holds no case for the
    report is on the no-case path, which this tree does not declare, so the
    path stage refuses the activity (HP-01-039).

    The sender must be a participant of the case (HP-01-006), and the
    declaration is adjudicated under the received-side RM acceptance rule
    before the commit (RSH-06-006, CLP-10-006): a backward move is refused, a
    non-adjacent forward one is recorded and flagged for the RSH-06-004 note.
    A guarded-commit subtree runs before the validation effects so receipt
    is recorded before any RM state transitions run (CLP-10-006).

    The validation subtree itself is built by
    :func:`~vultron.core.behaviors.report.validate_tree.create_validate_report_subtree`
    with ``emit=False`` — one definition shared with the trigger side
    (ARCH-15-004).  ``emit=False`` because the activity being handled *is* the
    ``validate-report`` message; re-emitting it would loop.  It records the
    participant write with ``rm_rule=RMRule.DECLARATION`` so the move the guard
    accepted is not refused at the write.

    Structure::

        ValidateReportReceivedBT (Sequence)
        ├── FindCaseForReport                       # publishes /case_id
        ├── [path stage, doors]                     # CASE_MANAGER path only
        ├── SenderIsParticipantNode                 # HP-01-006
        ├── Intake
        ├── AdjudicateRMDeclarationNode(VALID)      # RSH-06-006
        ├── GuardedCommitCaseLedgerEntryBT          # CLP-10-006
        ├── ValidateReportBT (Selector)
        │   ├── CheckRMStateValid(sender_actor_id)      # idempotency exit
        │   └── ValidationFlow (Sequence)
        │       ├── CheckRMStateReceivedOrInvalid(sender_actor_id)
        │       ├── EvaluateReportCredibility
        │       ├── EvaluateReportValidity
        │       ├── RequireCaseForReport                # the lookup found it
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
        case_published=True,
    )

    # RSH-08-003: the sender's RM → VALID is canonical participant state only
    # the CASE_MANAGER writes; ``validate_report`` is committed, then the
    # status it wrote follows as its own entry, which a replica copies from
    # the ledger fan-out, not from the direct Accept (#3814, CLP-07-013).
    # Every node below reads the case the lookup published.
    manager_effects = [
        validation,
        # The status the validation wrote, as its own entry (CLP-07-013).
        with_act_keys(
            CommitParticipantStatusEntriesNode(
                status_ids=written, name="RecordRMValidStatus"
            ),
            {SENDER_ID: sender_actor_id},
        ),
        rm_gap_note(sender_actor_id, None),
    ]
    root = create_receive_activity_tree(
        name="ValidateReportReceivedBT",
        case_id=None,
        case_lookup=with_act_keys(FindCaseForReport(), {REPORT_ID: report_id}),
        # The participant declares RM.VALID to the CASE_MANAGER alone, which
        # adjudicates and commits it (PCR-08-001, RSH-06-006); a participant
        # replica takes the sender's RM state from the ledger entry that
        # follows the act, never from the declaration itself (RSH-08-003),
        # so the path stage refuses a copy there (HP-01-005, HP-01-038).
        paths={ReceivedPath.CASE_MANAGER},
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(sender_id=sender_actor_id),
        precondition_guards=[
            rm_declaration_guard(sender_actor_id, RM.VALID, None),
        ],
        manager_effects=manager_effects,
        manager_gate_name="ValidateReportEffectsIfCaseManager",
        refusal_effects=[rm_gap_note(sender_actor_id, None)],
    )
    logger.debug(
        "Created ValidateReportReceivedBT for report=%s offer=%s sender=%s",
        report_id,
        offer_id,
        sender_actor_id,
    )
    return root
