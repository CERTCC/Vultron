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

"""Note-domain trigger activity construction for TriggerActivityAdapter."""

import logging

from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import OUTBOUND_DUMP_KWARGS
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronAlreadyExistsError, VultronNotFoundError
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    create_note_activity as build_create_note_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

from ._base import _addressing, _already_sealed, _seal

logger = logging.getLogger(__name__)


def _note_for_wire(dl: CasePersistence, note_id: str) -> as_Note:
    """Return the stored note *note_id* as the wire ``as_Note`` activities carry.

    Note is unpaired AS2 vocabulary: ``as_Note`` is a wire class of its own, so
    the core ``VultronNote`` that ``dl.read()`` returns for a stored note
    (DL-05-001) is not what ``_AddNoteToCaseActivity``'s ``as_Note``-typed
    ``object`` field accepts, although a generic ``as_Add`` admits any
    ``CoreObject``. ``Create`` gets the same wire note so the two agree. The translation
    belongs here on the adapter side (ARCH-20-001) and goes through the core
    object's AS2 rendering (ARCH-25-001, ADR-0099).

    Raises:
        VultronNotFoundError: when no object is stored under *note_id*.
        VultronValidationError: when the stored object is not a ``CoreObject``
            and so has no AS2 rendering.
        pydantic.ValidationError: when the stored object renders to something
            ``as_Note`` refuses (it is not a note).
    """
    stored = dl.read(note_id)
    if stored is None:
        raise VultronNotFoundError("Note", note_id)
    if isinstance(stored, as_Note):
        return stored
    return as_Note.model_validate(As2WireRenderAdapter().render(stored))


def _store_and_seal(
    dl: CaseOutboxPersistence, activity: as_Activity, method: str
) -> tuple[str, str]:
    """Store *activity* (once) and seal its outbound body; return ``(id, body)``.

    An activity already stored under its id is kept as it is and logged, so a
    re-run of *method* seals the body the first run stored (VM-08-003).
    """
    try:
        dl.create(activity)
    except VultronAlreadyExistsError:
        logger.warning(
            "%s: activity '%s' already exists — skipping", method, activity.id_
        )
    return _seal(dl, activity)


class _NotesMixin:
    """Trigger activity methods for Note objects."""

    _dl: CaseOutboxPersistence

    def create_note(
        self,
        name: str,
        content: str,
        context_id: str,
        attributed_to: str,
        in_reply_to: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist a Note object; return ``(note_id, note_dict)``."""
        note = as_Note(
            name=name,
            content=content,
            context=context_id,
            attributed_to=attributed_to,
            in_reply_to=in_reply_to,
        )
        try:
            self._dl.create(note)
        except VultronAlreadyExistsError:
            logger.warning(
                "create_note: note '%s' already exists — skipping", note.id_
            )
        return note.id_, note.model_dump_json(**OUTBOUND_DUMP_KWARGS)

    def create_note_activity(
        self,
        actor: str,
        note_id: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Create(Note)`` activity.

        The note's ``context`` names the case it belongs to; the ``Create``
        carries no ``target``
        (:func:`vultron.wire.as2.factories.create_note_activity`).  The id is
        derived from *actor* and the note, because one note is created once:
        a re-run hands back the body the first run sealed rather than queuing
        a second ``Create`` (ID-04-004, OX-06-002).

        Returns ``(activity_id, activity_body)``.

        Raises:
            VultronNotFoundError: when *note_id* is not in the DataLayer.
        """
        activity_id = derived_activity_id("note-created", actor, note_id)
        sealed = _already_sealed(self._dl, activity_id)
        if sealed is not None:
            return sealed
        activity = build_create_note_activity(
            _note_for_wire(self._dl, note_id),
            **_addressing(actor, to, activity_id),
        )
        return _store_and_seal(self._dl, activity, "create_note_activity")

    def add_note_to_case(
        self,
        note_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Add(Note, Case)`` activity."""
        note = _note_for_wire(self._dl, note_id)
        activity = add_note_to_case_activity(
            note=note, target=case_id, actor=actor, to=to
        )
        return _store_and_seal(self._dl, activity, "add_note_to_case")
