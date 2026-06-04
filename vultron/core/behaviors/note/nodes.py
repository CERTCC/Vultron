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
BT nodes for the note workflow.

Provides ``SaveNoteNode``, ``AttachNoteToCaseNode``, ``CreateNoteNode``, and
``AttachNoteFromResultNode``, composed into the note behavior trees.

Per specs/case-management.yaml CM-06.
"""

import logging
from typing import Any

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.note import VultronNote
from vultron.core.models.protocols import is_case_model
from vultron.core.use_cases._helpers import _as_id

logger = logging.getLogger(__name__)


class SaveNoteNode(DataLayerAction):
    """Persist a Note to the DataLayer using upsert semantics.

    Uses ``dl.save()`` so the operation is idempotent: calling it twice
    for the same note is safe.
    """

    def __init__(self, note_obj: VultronNote, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.note_obj = note_obj

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            self.datalayer.save(self.note_obj)
            self.logger.info(f"{self.name}: Saved note {self.note_obj.id_}")
            return Status.SUCCESS
        except Exception as e:
            self.logger.error(
                f"{self.name}: Error saving note {self.note_obj.id_}: {e}"
            )
            return Status.FAILURE


class AttachNoteToCaseNode(DataLayerAction):
    """Attach a note to a VulnerabilityCase in the DataLayer.

    Idempotent: if the note is already in ``case.notes``, the node
    succeeds without writing.  If *case_id* is ``None``, the node
    succeeds immediately (the note has no associated case).

    Per specs/case-management.yaml CM-06.
    """

    def __init__(
        self,
        note_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.note_id = note_id
        self.case_id = case_id

    def update(self) -> Status:
        if self.case_id is None:
            self.logger.debug(
                f"{self.name}: no case_id — skipping case attachment"
            )
            return Status.SUCCESS

        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        case: Any = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.logger.warning(
                f"{self.name}: case '{self.case_id}' not found"
                " — cannot attach note"
            )
            self.feedback_message = (
                f"case '{self.case_id}' not found in DataLayer"
            )
            return Status.FAILURE

        existing_ids = [_as_id(n) for n in case.notes]
        if self.note_id in existing_ids:
            self.logger.info(
                f"{self.name}: note '{self.note_id}' already in"
                f" case '{self.case_id}' — skipping (idempotent)"
            )
            return Status.SUCCESS

        case.notes.append(self.note_id)
        self.datalayer.save(case)
        self.logger.info(
            f"{self.name}: Attached note '{self.note_id}'"
            f" to case '{self.case_id}'"
        )
        return Status.SUCCESS


class CreateNoteNode(DataLayerAction):
    """Create and persist a Note via the TriggerActivityPort.

    Uses ``trigger_activity_factory`` from the blackboard to create the note
    object, then writes ``note_id`` and ``note_dict`` to *result_out* for use
    by downstream BT nodes and the enclosing use case.

    ``actor_id`` is read from the blackboard at execution time so the note is
    attributed to the requesting actor.

    Per specs/case-management.yaml CM-06; satisfies #712 AC-2.
    """

    def __init__(
        self,
        note_name: str,
        note_content: str,
        case_id: str,
        result_out: dict,
        in_reply_to: str | None = None,
        name: str | None = None,
    ):
        """
        Initialize CreateNoteNode.

        Args:
            note_name: Human-readable name/subject for the note.
            note_content: Full text content of the note.
            case_id: ID of the VulnerabilityCase the note belongs to.
            result_out: Mutable dict; ``note_id`` and ``note_dict`` are written
                here after successful creation so the enclosing use case can
                return them.
            in_reply_to: Optional ID of a parent note being replied to.
            name: Optional custom node name (defaults to class name).
        """
        super().__init__(name=name or self.__class__.__name__)
        self.note_name = note_name
        self.note_content = note_content
        self.case_id = case_id
        self.result_out = result_out
        self.in_reply_to = in_reply_to

    def update(self) -> Status:
        """Create note via TriggerActivityPort and store result in result_out.

        Returns:
            SUCCESS if note created, FAILURE if factory unavailable or error
        """
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            self.logger.error(f"{self.name}: {self.feedback_message}")
            return Status.FAILURE

        if self.trigger_activity_factory is None:
            self.feedback_message = (
                "trigger_activity_factory not available in blackboard"
            )
            self.logger.error(f"{self.name}: {self.feedback_message}")
            return Status.FAILURE

        if self.actor_id is None:
            self.feedback_message = "actor_id not available in blackboard"
            self.logger.error(f"{self.name}: {self.feedback_message}")
            return Status.FAILURE

        try:
            note_id, note_dict = self.trigger_activity_factory.create_note(
                name=self.note_name,
                content=self.note_content,
                context_id=self.case_id,
                attributed_to=self.actor_id,
                in_reply_to=self.in_reply_to,
            )
            self.result_out["note_id"] = note_id
            self.result_out["note_dict"] = note_dict
            self.feedback_message = f"Created note '{note_id}'"
            self.logger.info(f"{self.name}: {self.feedback_message}")
            return Status.SUCCESS
        except Exception as e:
            self.feedback_message = f"Error creating note: {e}"
            self.logger.error(f"{self.name}: {self.feedback_message}")
            return Status.FAILURE


class AttachNoteFromResultNode(DataLayerAction):
    """Attach a note to a VulnerabilityCase, reading note_id from result_out.

    Reads ``note_id`` from *result_out* at execution time, allowing it to be
    used downstream of a ``CreateNoteNode`` in the same BT Sequence without
    requiring the note_id to be known at tree construction time.

    Idempotent: if the note is already attached, the node succeeds without
    writing.

    Per specs/case-management.yaml CM-06; satisfies #712 AC-2.
    """

    def __init__(
        self,
        case_id: str,
        result_out: dict,
        name: str | None = None,
    ):
        """
        Initialize AttachNoteFromResultNode.

        Args:
            case_id: ID of the VulnerabilityCase to attach the note to.
            result_out: Shared dict containing ``note_id`` written by the
                preceding ``CreateNoteNode``.
            name: Optional custom node name (defaults to class name).
        """
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.result_out = result_out

    def update(self) -> Status:
        """Attach note from result_out to case in DataLayer.

        Returns:
            SUCCESS if attached (or already attached), FAILURE on error
        """
        note_id = self.result_out.get("note_id")
        if not note_id:
            self.feedback_message = "note_id not available in result_out"
            self.logger.error(f"{self.name}: {self.feedback_message}")
            return Status.FAILURE

        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            self.logger.error(f"{self.name}: {self.feedback_message}")
            return Status.FAILURE

        case: Any = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"case '{self.case_id}' not found"
            self.logger.warning(f"{self.name}: {self.feedback_message}")
            return Status.FAILURE

        existing_ids = [_as_id(n) for n in case.notes]
        if note_id in existing_ids:
            self.logger.info(
                f"{self.name}: note '{note_id}' already in"
                f" case '{self.case_id}' — skipping (idempotent)"
            )
            return Status.SUCCESS

        case.notes.append(note_id)
        self.datalayer.save(case)
        self.logger.info(
            f"{self.name}: Attached note '{note_id}' to case '{self.case_id}'"
        )
        return Status.SUCCESS
