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
    ├─ GuardedCommitCaseLedgerEntryBT  # CASE_MANAGER commits create_note
    ├─ SaveNoteNode                    # Upsert note (idempotent)
    └─ AttachNoteToCaseIfCaseManager
       └─ AttachNoteToCaseNode         # Attach note to case (idempotent)

A note that names no case has no commit and no attach stage.

Per specs/case-management.yaml CM-06 and
specs/case-ledger-processing.yaml CLP-07-013.
"""

import logging

import py_trees

from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.note.nodes import (
    AttachNoteToCaseNode,
    SaveNoteNode,
)
from vultron.core.models.note import VultronNote

logger = logging.getLogger(__name__)


def create_note_tree(
    note_obj: VultronNote,
    case_id: str | None,
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
            Create activity.
        case_id: The VulnerabilityCase ID to attach the note to, or ``None``
            if the note is not associated with any case.

    Returns:
        Root node of the CreateNoteBT behavior tree (Sequence).
    """
    # SaveNoteNode upserts the Note object itself, which every replica keeps
    # (CLP-10-017).  Attaching it to the case is a change to the case file
    # that only the CASE_MANAGER makes (RSH-08-003), and a change with no
    # committed entry is not made (CLP-07-013): the Create(Note) states the
    # attachment through the note's ``context``, so its own entry
    # (``create_note``) is the attachment's entry, and a replica attaches the
    # note when it applies that entry (``IsAddNoteEventNode`` slot, #4441).  A
    # note that names no case changes no case file, so the commit and the
    # gated attach are omitted entirely then.
    manager_effects: list[py_trees.behaviour.Behaviour] = []
    if case_id is not None:
        manager_effects.append(
            AttachNoteToCaseNode(note_id=note_obj.id_, case_id=case_id)
        )
    names_a_case = bool(manager_effects)
    root = create_receive_activity_tree(
        name="CreateNoteBT",
        case_id=case_id,
        precondition_guards=[],
        # A receiver that does not hold the named case is simply not its
        # CASE_MANAGER (not a Regime-1 anomaly): it keeps the Note object but
        # commits and attaches nothing, and takes the attachment from the
        # ledger (RSH-08-003, ADR-0087 Regime 3).
        case_may_be_absent=names_a_case,
        replica_effects=[SaveNoteNode(note_obj=note_obj)],
        manager_effects=manager_effects or None,
        manager_case_id=case_id,
        manager_gate_name=(
            "AttachNoteToCaseIfCaseManager" if names_a_case else None
        ),
        manager_case_may_be_absent=names_a_case,
    )
    logger.info(
        "Created CreateNoteBT for note=%s, case=%s", note_obj.id_, case_id
    )
    return root
