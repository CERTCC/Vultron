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

import json
import logging
from typing import cast

import py_trees.behaviour

from vultron.core.behaviors.note.add_note_trigger_tree import (
    add_note_to_case_trigger_bt,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.pending_assertion import ASSERTED_ACTIVITY_KEY
from vultron.core.models.use_case_result import NoteResult
from vultron.core.predicates.addressing import same_actor_id
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AddNoteToCaseTriggerRequest,
)

logger = logging.getLogger(__name__)


class SvcAddNoteToCaseUseCase(SvcBTTriggerBase[NoteResult]):
    """Add a note to a case (actor-initiated).

    Creates the note in the actor's datalayer with the case as its
    ``context``, adds it to the actor's local copy of the case, and queues
    one ``Create(Note)`` in the actor's outbox for delivery to the
    CASE_MANAGER.  The ``Create`` has no ``target``: the note's ``context``
    names the case, and the CASE_MANAGER attaches the note and commits a
    ``create_note`` entry from it, which replicas apply.  Sending a separate
    ``Add(Note, target=Case)`` as well is a valid protocol form that receivers
    accept, but this trigger does not use it, so one note makes one entry.

    Routing (CASE_MANAGER resolution), activity construction, and outbox
    queueing are delegated to :func:`sender_side_bt` per PCR-08-001.

    After successful activity queueing, records the ``Create(Note)`` in the
    actor's pending-assertion store under ``create_note``; the matching
    ``Announce(CaseLedgerEntry)`` clears it (SYNC-11-002, SYNC-11-003).
    Unlike the add-object trigger, this one suppresses no repeat: every run
    mints a new note, so a second request is a second note, never a repeat
    of a pending assertion.

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
            create_id, create_body = self._factory.create_note_activity(
                actor=self._actor_id,
                note_id=note_id,
                to=[case_manager_id],
            )
            self._captured["activity"] = json.loads(create_body)
            # The CASE_MANAGER keeps no pending assertion for its own case:
            # its commit is the authoritative write (SYNC-11-004).
            if not same_actor_id(case_manager_id, self._actor_id):
                self._result_out[ASSERTED_ACTIVITY_KEY] = create_id
            return [create_id]

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
        self._record_asserted_activity(
            self._case_id, MessageSemantics.CREATE_NOTE.value
        )

    def _build_result(self) -> NoteResult:
        """The activity body plus the note the tree minted."""
        return NoteResult(
            **self._activity_fields(), note=self._captured.get("note")
        )
