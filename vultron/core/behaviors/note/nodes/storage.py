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

from typing import ClassVar

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.reference_list import (
    CaseReferenceEditNode,
    ReferenceField,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.idempotency import FlaggedRepeatGuardMixin
from vultron.core.models.note import VultronNote
from vultron.core.sync_helpers import is_ledgered_activity


class SaveNoteNode(DataLayerActionWithPorts):
    """Persist a Note to the DataLayer using upsert semantics."""

    def __init__(self, note_obj: VultronNote, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.note_obj = note_obj

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        try:
            self.datalayer.save(self.note_obj)
            self.logger.info("%s: Saved note %s", self.name, self.note_obj.id_)
            return Status.SUCCESS
        except Exception as e:  # noqa: BLE001  # ruff-baseline #3768
            self.logger.error(  # noqa: TRY400  # ruff-baseline #3353
                "%s: Error saving note %s: %s", self.name, self.note_obj.id_, e
            )
            return Status.FAILURE


class StoreNoteIfAbsentNode(SaveNoteNode):
    """Persist a Note only when no record is stored under its id.

    The received ``Add(Note)`` tree uses this in place of the upsert
    :class:`SaveNoteNode`: an ``Add`` brings a note the CASE_MANAGER may
    not hold yet, but it never replaces one already stored under that id
    (HP-08-006).  In the received tree :class:`NoteIdNotTakenNode` has
    already refused an ``Add`` naming a stored note; this node still never
    overwrites one.
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if self.datalayer.read(self.note_obj.id_) is not None:
            self.logger.debug(
                "%s: note %s already stored; kept as stored",
                self.name,
                self.note_obj.id_,
            )
            return Status.SUCCESS
        return super().update()


class NoteIdNotTakenNode(FlaggedRepeatGuardMixin, DataLayerConditionWithPorts):
    """Guard: no note is stored under the received note's id yet.

    An ``Add(Note)`` introduces a new note (VAM-01-010, HP-08-006); a change
    to a stored note is an ``Update(Note)``.  So a note already stored under
    the id refuses the ``Add``, whatever the carried copy says: the inbox's
    routing rebuild hands this guard the stored note in place of the carried
    one (IO-03-004), so comparing the two could never see a difference.

    A **redelivery** of the ``Add`` the case's ledger already records (the
    same *activity_id*) is not a refusal (HP-01-003): the guard sets
    :attr:`is_redelivery` and fails, so nothing downstream runs, and the
    handler reports the run as ``SKIPPED``.  Read-only, so it runs before
    the guarded commit (CLP-10-006).
    """

    _REPEAT_FLAG = "is_redelivery"

    def __init__(
        self,
        note_id: str,
        case_id: str,
        activity_id: str,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.note_id = note_id
        self.case_id = case_id
        self.activity_id = activity_id
        self.is_redelivery = False
        """``True`` when the last run found this Add already ledgered: a
        benign no-op, not a refusal."""

    def update(self) -> Status:
        self.is_redelivery = False
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if self.datalayer.read(self.note_id) is None:
            return Status.SUCCESS
        if is_ledgered_activity(
            self.datalayer, self.case_id, self.activity_id
        ):
            self.is_redelivery = True
            self.feedback_message = (
                f"Add(Note) '{self.activity_id}' is already recorded for case"
                f" '{self.case_id}' — redelivery, nothing to apply (HP-01-003)"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        self.feedback_message = (
            f"a note is already stored as '{self.note_id}'; an Add(Note)"
            " introduces a new note, and a change to one is an Update(Note)"
            " — REFUSED (HP-08-006)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class AttachNoteToCaseNode(CaseReferenceEditNode):
    """Attach a note to a VulnerabilityCase in the DataLayer (idempotent)."""

    FIELD: ClassVar[ReferenceField] = "notes"
    ATTACH: ClassVar[bool] = True

    def __init__(
        self,
        note_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(ref_id=note_id, case_id=case_id, name=name)
        self.note_id = note_id


class DetachNoteFromCaseNode(CaseReferenceEditNode):
    """Remove a note from a VulnerabilityCase's ``notes`` (idempotent)."""

    FIELD: ClassVar[ReferenceField] = "notes"
    ATTACH: ClassVar[bool] = False

    def __init__(
        self,
        note_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(ref_id=note_id, case_id=case_id, name=name)
        self.note_id = note_id
