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
from vultron.core.models._helpers import _as_id
from vultron.core.models.note import VultronNote


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
    (HP-08-006).  :class:`NoteIdNotTakenNode` decides whether a stored note
    is the same note; this node keeps every field of the stored one either
    way, including the fields the guard does not compare.
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


#: The fields that make two notes the same note: what it says, who wrote it,
#: which case it belongs to and what it answers.
_NOTE_IDENTITY_FIELDS: tuple[str, ...] = (
    "name",
    "content",
    "attributed_to",
    "context",
    "in_reply_to",
)


def _note_identity(note: object) -> tuple[object, ...]:
    return tuple(
        _as_id(getattr(note, field, None)) for field in _NOTE_IDENTITY_FIELDS
    )


class NoteIdNotTakenNode(DataLayerConditionWithPorts):
    """Guard: no different note is stored under the received note's id.

    A received ``Add(Note)`` carries its note inline, and the CASE_MANAGER
    stores that note before attaching it (VAM-01-010, HP-08-006).  A note
    already stored under the same id passes only when it is the same note
    (same name, content, author, case and reply target), as on a
    redelivery; otherwise the ``Add`` would overwrite another note and the
    ledger entry would carry the overwrite to every replica, so the guard
    refuses it.  Read-only, so it runs before the guarded commit
    (CLP-10-006).

    The guard sees a difference only when the carried note reaches core.
    The inbox ingress stores no inline object (IO-03-004), but its routing
    rebuild prefers a record already stored under the note's id, so the
    rehydrated ``Add`` holds the stored note and the guard passes;
    :class:`StoreNoteIfAbsentNode` keeps the stored note on every path.
    """

    def __init__(self, note_obj: VultronNote, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.note_obj = note_obj

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        stored = self.datalayer.read(self.note_obj.id_)
        if stored is None or _note_identity(stored) == _note_identity(
            self.note_obj
        ):
            return Status.SUCCESS
        self.feedback_message = (
            f"a different note is already stored as '{self.note_obj.id_}';"
            " the Add(Note) would overwrite it — REFUSED (HP-08-006)"
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
