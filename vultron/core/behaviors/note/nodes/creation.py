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

"""Creation-oriented note BT nodes."""

from typing import Any

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.protocols import is_case_model
from vultron.core.use_cases._helpers import _as_id


class CreateNoteNode(DataLayerAction):
    """Create and persist a Note via the TriggerActivityPort."""

    def __init__(
        self,
        note_name: str,
        note_content: str,
        case_id: str,
        result_out: dict,
        in_reply_to: str | None = None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.note_name = note_name
        self.note_content = note_content
        self.case_id = case_id
        self.result_out = result_out
        self.in_reply_to = in_reply_to

    def _call_factory(self, actor_id: str) -> tuple[str, dict]:
        """Call ``create_note`` on the trigger-activity factory."""
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.create_note(
            name=self.note_name,
            content=self.note_content,
            context_id=self.case_id,
            attributed_to=actor_id,
            in_reply_to=self.in_reply_to,
        )

    def update(self) -> Status:
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
            note_id, note_dict = self._call_factory(self.actor_id)
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
    """Attach a note to a case, reading ``note_id`` from ``result_out``."""

    def __init__(
        self,
        case_id: str,
        result_out: dict,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.result_out = result_out

    def update(self) -> Status:
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
