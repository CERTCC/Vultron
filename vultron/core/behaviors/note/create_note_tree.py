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
Note creation behavior tree composition.

Composes the create_note workflow as a behavior tree.  The tree saves the
note to the DataLayer and, when the note carries a ``context`` (case ID),
commits the ``Create(Note)`` as the case's ledger entry and attaches the note
to the associated VulnerabilityCase, both only at the case's CASE_MANAGER.

Structure (when the note names a case):

    CreateNoteBT (Sequence, via create_receive_activity_tree)
    ├─ IntakeReceivedActivityNode      # Archive the Create(Note) as received
    ├─ CaseOpenToExternalWrites        # Post-close write boundary
    ├─ SenderRuleGuard                 # Composed from the declared rule
    ├─ CaseManagerGate[ClockDecisionStage]  # Embargo end-time check
    ├─ GuardedCommitCaseLedgerEntryBT  # CASE_MANAGER commits create_note
    ├─ SaveNoteNode                    # Upsert note (idempotent)
    └─ AttachNoteToCaseIfCaseManager
       └─ AttachNoteToCaseNode         # Attach note to case (idempotent)

A note that names no case, or a case this store does not hold, is refused by
the sender guard: no sender has standing outside a case (HP-01-008).  A
``Create(Note)`` that carries no note is refused by the same tree's guard
instead (``ActivityIncompleteNode``), so the delivery still runs one tree and
is archived (CLP-10-005, CLP-10-018).

Per specs/case-management.yaml CM-06 and
specs/case-ledger-processing.yaml CLP-07-013.
"""

import logging

import py_trees

from vultron.core.behaviors.case.intake_only_received_tree import (
    create_incomplete_activity_received_tree,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.note.nodes import (
    AttachNoteToCaseNode,
    SaveNoteNode,
)
from vultron.core.behaviors.sender_check_context import SenderCheckContext
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.models.note import VultronNote

logger = logging.getLogger(__name__)


def create_note_tree(
    note_obj: VultronNote | None,
    case_id: str | None,
    sender_id: str,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the behavior tree for the create_note workflow.

    Handles receipt of a ``Create(Note)`` activity: persists the note to the
    DataLayer and, when the note specifies a case context, has the case's
    CASE_MANAGER commit the activity as a ledger entry and attach the note to
    the VulnerabilityCase.

    Each step is idempotent, so replaying the same activity yields the same
    outcome without duplication.

    Args:
        note_obj: The VultronNote domain object extracted from the inbound
            Create activity; ``None`` when the activity carries none, which
            the tree refuses.
        case_id: The VulnerabilityCase ID to attach the note to, or ``None``
            if the note names no case, which the sender guard refuses.
        sender_id: The ``Create(Note)``'s sender.
        sender_rule: The use case's declared sender rule (HP-01-008).  At a
            participant replica the sender must be the CASE_MANAGER this
            store knows for the case, so a case it does not hold refuses
            (``case_manager_required``, PCR-03-001).

    Returns:
        Root node of the CreateNoteBT behavior tree (Sequence).
    """
    if note_obj is None:
        return create_incomplete_activity_received_tree(
            "CreateNoteBT", "Create(Note) carries no note object"
        )
    # SaveNoteNode upserts the Note object itself, which every replica keeps
    # (CLP-10-017).  Attaching it to the case is a change to the case file
    # that only the CASE_MANAGER makes (RSH-08-003), and a change with no
    # committed entry is not made (CLP-07-013): the Create(Note) states the
    # attachment through the note's ``context``, so its own entry
    # (``create_note``) is the attachment's entry, and a replica attaches the
    # note when it applies that entry (``IsAddNoteEventNode`` slot, #4441).
    # A note that names no case reaches neither: the sender guard refuses it.
    root = create_receive_activity_tree(
        name="CreateNoteBT",
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_id,
            case_id=case_id,
            case_manager_required=True,
        ),
        precondition_guards=[],
        replica_effects=[SaveNoteNode(note_obj=note_obj)],
        manager_effects=(
            [AttachNoteToCaseNode(note_id=note_obj.id_, case_id=case_id)]
            if case_id is not None
            else None
        ),
        manager_case_id=case_id,
        manager_gate_name=(
            "AttachNoteToCaseIfCaseManager" if case_id is not None else None
        ),
    )
    logger.info(
        "Created CreateNoteBT for note=%s, case=%s", note_obj.id_, case_id
    )
    return root
