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
attaches it to the associated VulnerabilityCase.

Structure:

    CreateNoteBT (Sequence)
    ├─ SaveNoteNode          # Upsert note into DataLayer (idempotent)
    └─ AttachNoteToCaseNode  # Attach note to case if case_id present (idempotent)

Per specs/case-management.md CM-06.
"""

import logging

import py_trees

from vultron.core.models.note import VultronNote
from vultron.core.behaviors.note.nodes import (
    AttachNoteToCaseNode,
    SaveNoteNode,
)

logger = logging.getLogger(__name__)


def create_note_tree(
    note_obj: VultronNote,
    case_id: str | None,
) -> py_trees.behaviour.Behaviour:
    """Create the behavior tree for the create_note workflow.

    Handles receipt of a ``Create(Note)`` activity: persists the note to the
    DataLayer and, when the note specifies a case context, attaches it to
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
    root = py_trees.composites.Sequence(
        name="CreateNoteBT",
        memory=False,
        children=[
            SaveNoteNode(note_obj=note_obj),
            AttachNoteToCaseNode(note_id=note_obj.id_, case_id=case_id),
        ],
    )
    logger.debug(
        f"Created CreateNoteBT for note={note_obj.id_}, case={case_id}"
    )
    return root
