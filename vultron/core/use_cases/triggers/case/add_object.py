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

import json
import logging
from typing import Any, cast

import py_trees.behaviour

from vultron.core.behaviors.case.add_object_trigger_tree import (
    add_object_trigger_bt,
)
from vultron.core.models.pending_assertion import ASSERTED_ACTIVITY_KEY
from vultron.core.models.use_case_result import ActivityResult
from vultron.core.predicates.addressing import same_actor_id
from vultron.core.use_cases.triggers._base import SvcActivityTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AddObjectToCaseTriggerRequest,
)
from vultron.errors import (
    VultronActivityConstructionError,
    VultronNotFoundError,
    VultronValidationError,
)

logger = logging.getLogger(__name__)


class SvcAddObjectToCaseUseCase(SvcActivityTriggerBase):
    """Add any existing AS2 object to a case (general-purpose).

    Reads the object by ``object_id`` from the datalayer, creates a generic
    ``Add(object, target=case)`` activity addressed to the case's
    CASE_MANAGER alone (PCR-08-005), and queues it in the actor's outbox.
    The object must already exist; this use case does not create it.

    Before anything is built, the ``Add`` is classified the way a receiver
    would classify it.  An object type no receive-side pattern routes as an
    addition to the case, or one with its own flow (``EmbargoEvent``,
    ``CaseParticipant``, ``CaseStatus``), is refused with
    ``VultronValidationError`` (422) and nothing is queued (TRIG-10-001).
    A case with no CASE_MANAGER fails the same way, also before the outbox
    is written.

    After queueing, the ``Add`` is recorded in the actor's pending-assertion
    store under its semantics, the semantic type the CASE_MANAGER commits; the
    matching ``Announce(CaseLedgerEntry)`` clears it (SYNC-11-002,
    SYNC-11-003).  Adding the same object to the same case again while that
    assertion is pending is suppressed before the tree runs and reported with
    no activity (:meth:`_suppressed_duplicate`).

    Type-specific wrappers (e.g., ``SvcAddReportToCaseUseCase``) subclass
    this and replace only :meth:`_prepare` (TRIG-10-002).

    Implements: TRIG-10-001.

    BT-15-001 audit: routing, ``Add`` construction and outbox queueing are
    delegated to :func:`sender_side_bt` (PCR-08-001).
    """

    def _prepare(self) -> None:
        request = cast(AddObjectToCaseTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._case_id = resolve_case(request.case_id, self._dl).id_
        self._object_id: str = request.object_id
        if self._dl.read(self._object_id) is None:
            raise VultronNotFoundError("AS2Object", self._object_id)

    def _suppressed_duplicate(self) -> ActivityResult | None:
        # Classify first: a refused type raises here, before any tree exists,
        # so it queues nothing.  The semantics is also the ledger semantic type
        # the pending assertion is keyed by.
        try:
            self._semantics = self._factory.add_object_to_case_semantics(
                object_id=self._object_id, case_id=self._case_id
            )
        except VultronActivityConstructionError as exc:
            # A stored object with no wire form (a bookkeeping record, an
            # abstract actor) is the caller's bad request, not a server
            # fault: refused as 422 like any other unroutable type.
            raise VultronValidationError(str(exc)) from exc
        return self._suppressed_repeat(
            self._case_id, self._semantics.value, self._object_id
        )

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activities(case_manager_id: str) -> list[str]:
            add_id, add_body = self._factory.add_object_to_case(
                actor=self._actor_id,
                object_id=self._object_id,
                case_id=self._case_id,
                to=[case_manager_id],
            )
            self._captured["activity"] = json.loads(add_body)
            # The CASE_MANAGER keeps no pending assertion for its own case:
            # its commit is the authoritative write (SYNC-11-004).
            if not same_actor_id(case_manager_id, self._actor_id):
                self._result_out[ASSERTED_ACTIVITY_KEY] = add_id
            return [add_id]

        return add_object_trigger_bt(
            case_id=self._case_id, activity_builder=_build_activities
        )

    def _extra_execute_kwargs(self) -> dict[str, Any]:
        return {"case_id": self._case_id}

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' added object '%s' to case '%s'",
            self._actor_id,
            self._object_id,
            self._case_id,
        )
        self._record_asserted_activity(
            self._case_id, self._semantics.value, subject_id=self._object_id
        )
