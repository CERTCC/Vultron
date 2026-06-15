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
from typing import TYPE_CHECKING

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.note.add_note_trigger_tree import (
    add_note_to_case_trigger_bt,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.pending_assertion import get_pending_assertion_store
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.errors import VultronValidationError
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AddNoteToCaseTriggerRequest,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class SvcAddNoteToCaseUseCase:
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
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddNoteToCaseTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        resolve_case(case_id, dl)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcAddNoteToCaseUseCase requires a TriggerActivityPort"
            )
        factory = self._trigger_activity

        # result_out is written by CreateNoteNode and AttachNoteFromResultNode
        # inside the BT; the closure and the return statement read from it.
        result_out: dict = {}

        def _build_activities(case_manager_id: str) -> list[str]:
            note_id = result_out["note_id"]
            create_id = factory.create_note_activity(
                actor=actor_id,
                note_id=note_id,
                to=[case_manager_id],
            )
            add_id, add_dict = factory.add_note_to_case(
                note_id=note_id,
                case_id=case_id,
                actor=actor_id,
                to=[case_manager_id],
            )
            result_out["activity"] = add_dict
            result_out["add_activity_id"] = add_id
            return [create_id, add_id]

        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        tree = add_note_to_case_trigger_bt(
            case_id=case_id,
            note_name=request.note_name,
            note_content=request.note_content,
            in_reply_to=request.in_reply_to,
            result_out=result_out,
            activity_builder=_build_activities,
        )
        result_status = bridge.execute_with_setup(tree, actor_id=actor_id)

        if result_status.status != Status.SUCCESS:
            raise VultronValidationError(
                f"AddNoteToCase failed: {BTBridge.get_failure_reason(tree)}"
            )

        note_id = result_out.get("note_id", "")
        logger.info(
            "Actor '%s' added note '%s' to case '%s'",
            actor_id,
            note_id,
            case_id,
        )

        # Record the Add(Note,Case) activity in the pending-assertion store so
        # that duplicate near-term re-emits are suppressed until the matching
        # Announce(CaseLedgerEntry) confirms the round-trip (SYNC-11-002).
        add_activity_id = result_out.get("add_activity_id", "")
        if add_activity_id:
            store = get_pending_assertion_store(actor_id)
            store.add(
                case_id,
                MessageSemantics.ADD_NOTE_TO_CASE.value,
                add_activity_id,
            )

        return {
            "note": result_out.get("note_dict"),
            "activity": result_out.get("activity"),
        }
