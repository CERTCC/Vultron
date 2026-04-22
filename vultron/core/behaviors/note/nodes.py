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

Provides ``SaveNoteNode`` and ``AttachNoteToCaseNode``, composed by
``create_note_tree`` into the ``CreateNoteBT`` behavior tree.

Per specs/case-management.md CM-06.
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

    Per specs/case-management.md CM-06.
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
