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
Class-based use case for the add-note-to-case trigger behavior.

No HTTP framework imports permitted here.
"""

import logging

from vultron.core.models.protocols import is_case_model
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases._helpers import case_addressees
from vultron.core.use_cases.triggers._helpers import (
    add_activity_to_outbox,
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AddNoteToCaseTriggerRequest,
)
from vultron.wire.as2.vocab.activities.case import AddNoteToCaseActivity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

logger = logging.getLogger(__name__)


class SvcAddNoteToCaseUseCase:
    """Add a note to a case (actor-initiated).

    Creates the note in the actor's datalayer, adds it to the actor's local
    copy of the case, and queues Create(Note) and AddNoteToCase(Note, Case)
    activities in the actor's outbox for delivery to case participants.
    """

    def __init__(
        self, dl: CaseOutboxPersistence, request: AddNoteToCaseTriggerRequest
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        case = resolve_case(case_id, dl)

        note = as_Note(
            name=request.note_name,
            content=request.note_content,
            context=case_id,
            attributed_to=actor_id,
            in_reply_to=request.in_reply_to,
        )

        try:
            dl.create(note)
        except ValueError:
            logger.warning(
                "AddNoteToCase: note '%s' already exists — skipping create",
                note.id_,
            )

        # Add note to the actor's local copy of the case.
        case_obj = dl.read(case_id)
        if is_case_model(case_obj):
            existing_ids = [
                n if isinstance(n, str) else getattr(n, "id_", str(n))
                for n in case_obj.notes
            ]
            if note.id_ not in existing_ids:
                case_obj.notes.append(note.id_)
                dl.save(case_obj)
                logger.debug(
                    "AddNoteToCase: added note '%s' to local case '%s'",
                    note.id_,
                    case_id,
                )

        addressees = case_addressees(case, actor_id) or None

        create_activity = as_Create(
            actor=actor_id,
            object_=note,
            to=addressees,
        )
        add_note_activity = AddNoteToCaseActivity(
            actor=actor_id,
            object_=note,
            target=case_id,
            to=addressees,
        )

        for activity in (create_activity, add_note_activity):
            try:
                dl.create(activity)
            except ValueError:
                logger.warning(
                    "AddNoteToCase: activity '%s' already exists — skipping",
                    activity.id_,
                )
            add_activity_to_outbox(actor_id, activity.id_, dl)

        logger.info(
            "Actor '%s' added note '%s' to case '%s'",
            actor_id,
            note.id_,
            case_id,
        )

        return {
            "note": note.model_dump(by_alias=True, exclude_none=True),
            "activity": add_note_activity.model_dump(
                by_alias=True, exclude_none=True
            ),
        }
