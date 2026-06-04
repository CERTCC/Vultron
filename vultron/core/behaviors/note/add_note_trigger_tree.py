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
Trigger-side behavior tree for the add-note-to-case workflow.

The tree runs three steps in sequence:

1. **CreateNoteNode** — calls ``TriggerActivityPort.create_note()`` via the
   blackboard factory, persists the note, and writes ``note_id``/``note_dict``
   to *result_out*.
2. **AttachNoteFromResultNode** — reads ``note_id`` from *result_out* and
   appends it to the case's ``notes`` list (idempotent).
3. **sender_side_bt** — resolves the Case Manager, constructs the outbound
   ``Add(Note, Case)`` activity, and queues it in the actor's outbox
   (PCR-08-001).

This refactoring satisfies #712 AC-2: all protocol-significant domain work
(note creation, persistence, case attachment) is performed inside the BT so
it is visible to BT analysis and auditing tools.
"""

from typing import Callable

import py_trees

from vultron.core.behaviors.note.nodes import (
    AttachNoteFromResultNode,
    CreateNoteNode,
)
from vultron.core.behaviors.sender.send_tree import sender_side_bt


def add_note_to_case_trigger_bt(
    case_id: str,
    note_name: str,
    note_content: str,
    result_out: dict,
    activity_builder: Callable[[str], list[str]],
    in_reply_to: str | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the add-note-to-case workflow.

    Args:
        case_id: ID of the VulnerabilityCase to attach the note to.
        note_name: Human-readable name/subject for the note.
        note_content: Full text content of the note.
        result_out: Mutable dict; ``note_id`` and ``note_dict`` are written by
            ``CreateNoteNode`` so the enclosing use case can return them and
            the ``activity_builder`` closure can read ``note_id`` after it
            runs.
        activity_builder: Callable invoked by the sender subtree with the
            resolved Case Manager actor ID; should return a list of outbound
            activity IDs to queue.
        in_reply_to: Optional ID of a parent note being replied to.

    Returns:
        A ``py_trees.composites.Sequence`` that:

        - Creates and persists the note (via TriggerActivityPort).
        - Attaches the note to the local case copy.
        - Resolves the Case Manager, builds outbound activities, and queues
          them in the actor's outbox.
    """
    return py_trees.composites.Sequence(
        name="AddNoteToCaseTriggerBT",
        memory=False,
        children=[
            CreateNoteNode(
                note_name=note_name,
                note_content=note_content,
                case_id=case_id,
                result_out=result_out,
                in_reply_to=in_reply_to,
            ),
            AttachNoteFromResultNode(case_id=case_id, result_out=result_out),
            sender_side_bt(case_id=case_id, activity_builder=activity_builder),
        ],
    )
