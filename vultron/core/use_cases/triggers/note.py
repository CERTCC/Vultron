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
from typing import cast

import py_trees.behaviour

from vultron.core.behaviors.note.add_note_trigger_tree import (
    add_note_to_case_trigger_bt,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.pending_assertion import get_pending_assertion_store
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AddNoteToCaseTriggerRequest,
)

logger = logging.getLogger(__name__)


class SvcAddNoteToCaseUseCase(SvcBTTriggerBase):
    """Add a note to a case (actor-initiated).

    Creates the note in the actor's datalayer, adds it to the actor's local
    copy of the case, and queues Create(Note) and AddNoteToCase(Note, Case)
    activities in the actor's outbox for delivery to the Case Actor.

    Routing (CASE_MANAGER resolution), activity construction, and outbox
    queueing are delegated to :func:`sender_side_bt` per PCR-08-001.

    After successful activity queueing, records the Add(Note,Case) activity
    in the actor's pending-assertion store so that duplicate near-term
    re-emits are suppressed until the matching Announce(CaseLedgerEntry)
    arrives (SYNC-11-002).

    The return value extends the base-class ``{"activity": ...}`` dict with
    a ``"note"`` key for the created Note object.
    """

    def _prepare(self) -> None:
        request = cast(AddNoteToCaseTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._case_id = request.case_id
        resolve_case(request.case_id, self._dl)

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        request = cast(AddNoteToCaseTriggerRequest, self._request)

        def _build_activities(case_manager_id: str) -> list[str]:
            note_id = str(self._result_out["note_id"])
            create_id = self._factory.create_note_activity(
                actor=self._actor_id,
                note_id=note_id,
                to=[case_manager_id],
            )
            add_id, add_dict = self._factory.add_note_to_case(
                note_id=note_id,
                case_id=self._case_id,
                actor=self._actor_id,
                to=[case_manager_id],
            )
            self._captured["activity"] = add_dict
            self._result_out["add_activity_id"] = add_id
            return [create_id, add_id]

        return add_note_to_case_trigger_bt(
            case_id=self._case_id,
            note_name=request.note_name,
            note_content=request.note_content,
            in_reply_to=request.in_reply_to,
            result_out=self._result_out,
            activity_builder=_build_activities,
        )

    def _handle_result(self) -> None:
        self._captured["note"] = self._result_out.get("note_dict")
        note_id = self._result_out.get("note_id", "")
        logger.info(
            "Actor '%s' added note '%s' to case '%s'",
            self._actor_id,
            note_id,
            self._case_id,
        )
        add_activity_id = str(self._result_out.get("add_activity_id", ""))
        if add_activity_id:
            store = get_pending_assertion_store(self._actor_id)
            store.add(
                self._case_id,
                MessageSemantics.ADD_NOTE_TO_CASE.value,
                add_activity_id,
            )

    def execute(self) -> dict:
        """Execute and return ``{"note": ..., "activity": ...}``."""
        result = super().execute()
        result["note"] = self._captured.get("note")
        return result
