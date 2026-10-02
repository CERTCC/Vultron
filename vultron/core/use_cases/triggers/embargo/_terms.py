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

"""Shared frame for the two triggers that offer embargo terms.

``propose`` and ``revise`` differ only in the tree they run (a revision first
asserts an embargo is active) and in what they log.  Both build an
``Invite(EmbargoEvent)``: to the CASE_MANAGER when the actor is not the role
holder, and — as the CASE_MANAGER — addressed to nobody and committed, before
the relay invites each participant (EP-09-008, EP-09-002).
"""

import json
from collections.abc import Callable
from typing import ClassVar, cast

import py_trees.behaviour

from vultron.core.behaviors.embargo.nodes import EMBARGO_INVITE_EVENT_TYPE
from vultron.core.behaviors.embargo.proposal_index import (
    record_embargo_proposal_index,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.pending_assertion import ASSERTED_ACTIVITY_KEY
from vultron.core.use_cases.triggers._base import SvcEmbargoTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    ProposeEmbargoRevisionTriggerRequest,
    ProposeEmbargoTriggerRequest,
)


class SvcOfferEmbargoTermsBase(SvcEmbargoTriggerBase):
    """Prepare, build and index an embargo proposal (propose or revise).

    Subclasses name the tree factory; its signature is the one
    ``propose_embargo_trigger_bt`` and ``propose_embargo_revision_trigger_bt``
    share.
    """

    _assertion_event_type: ClassVar[str] = EMBARGO_INVITE_EVENT_TYPE
    _tree_factory: ClassVar[Callable[..., py_trees.behaviour.Behaviour]]

    def _prepare(self) -> None:
        request = cast(
            ProposeEmbargoTriggerRequest
            | ProposeEmbargoRevisionTriggerRequest,
            self._request,
        )
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._case = resolve_case(request.case_id, self._dl)
        self._embargo = EmbargoEvent(
            context=self._case.id_, end_time=request.end_time
        )

    def _assertion_subject(self) -> str:
        # A new EmbargoEvent id is minted per call, so the terms are what a
        # repeated proposal repeats.
        return self._embargo.end_time.isoformat()

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activity(to: list[str] | None) -> tuple[str, str]:
            proposal_id, proposal_blob = self._factory.propose_embargo(
                embargo_id=self._embargo.id_,
                case_id=self._case.id_,
                actor=self._actor_id,
                to=to,
            )
            self._captured["activity"] = json.loads(proposal_blob)
            self._captured["proposal_id"] = proposal_id
            return proposal_id, proposal_blob

        return type(self)._tree_factory(
            case_id=self._case.id_,
            actor_id=self._actor_id,
            embargo=self._embargo,
            result_out=self._result_out,
            activity_builder=_build_activity,
        )

    def _handle_result(self) -> None:
        super()._handle_result()
        if self._output_id(ASSERTED_ACTIVITY_KEY) is not None:
            return  # asked the CASE_MANAGER: its relay indexes the proposal
        # The CASE_MANAGER's own proposal is answered against this index, as
        # a proposal it received is (EP-09-001).
        proposal_id = self._captured.get("proposal_id")
        if isinstance(proposal_id, str) and proposal_id:
            record_embargo_proposal_index(
                self._dl, self._case.id_, self._embargo.id_, proposal_id
            )
