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
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

from ._base import _DUMP_KWARGS
from vultron.errors import VultronAlreadyExistsError, VultronNotFoundError

logger = logging.getLogger(__name__)


def _note_for_wire(dl: CasePersistence, note_id: str) -> as_Note:
    """Return the stored note *note_id* as the wire ``as_Note`` activities carry.

    Note is unpaired AS2 vocabulary: ``as_Note`` is a wire class of its own, so
    the core ``VultronNote`` that ``dl.read()`` returns for a stored note
    (DL-05-001) is not what ``_AddNoteToCaseActivity``'s ``as_Note``-typed
    ``object`` field accepts, although a generic ``as_Add`` admits any
    ``CoreObject``. ``Create`` gets the same wire note so the two agree. The translation
    belongs here on the adapter side (ARCH-12-005) and goes through the core
    object's AS2 rendering (ADR-0099 detail 1).

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
        return note.id_, note.model_dump_json(**_DUMP_KWARGS)

    def create_note_activity(
        self,
        actor: str,
        note_id: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist a ``Create(Note)`` activity; return activity_id."""
        note = _note_for_wire(self._dl, note_id)
        activity = as_Create(actor=actor, object_=note, to=to)
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "create_note_activity: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return activity.id_

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
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "add_note_to_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump_json(**_DUMP_KWARGS)
