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
from typing import Any, cast

from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

from ._base import _DUMP_KWARGS

logger = logging.getLogger(__name__)


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
    ) -> tuple[str, dict[str, Any]]:
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
        except ValueError:
            logger.warning(
                "create_note: note '%s' already exists — skipping", note.id_
            )
        return note.id_, note.model_dump(**_DUMP_KWARGS)

    def create_note_activity(
        self,
        actor: str,
        note_id: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist a ``Create(Note)`` activity; return activity_id."""
        note = cast(as_Note, self._dl.read(note_id))
        activity = as_Create(actor=actor, object_=note, to=to)
        try:
            self._dl.create(activity)
        except ValueError:
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
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Add(Note, Case)`` activity."""
        note = cast(as_Note, self._dl.read(note_id))
        activity = add_note_to_case_activity(
            note=note, target=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "add_note_to_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)
