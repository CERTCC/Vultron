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

"""Storage-oriented note BT nodes."""

from typing import Any

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.note import VultronNote


class SaveNoteNode(DataLayerAction):
    """Persist a Note to the DataLayer using upsert semantics."""

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
    """Attach a note to a VulnerabilityCase in the DataLayer."""

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
        if not isinstance(case, VulnerabilityCase):
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
