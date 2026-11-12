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

"""Embargo accept trigger use case.

A participant's accept is ``Accept(Invite(EmbargoEvent))``, its own consent.
The case owner's accept is its decision for the case,
``Add(EmbargoEvent)[target=VulnerabilityCase]``, which activates the proposal
(ADR-0180).  An owner whose row for the proposal reads ``DECLINED`` sends
the ``Accept(Invite(EmbargoEvent))`` instead: the CASE_MANAGER refuses its
activation until it has accepted (MSM-07-037), so its first accept changes
its answer and a later one activates.  The trigger reads the owner's own
store: an owner that is the CASE_MANAGER holds the Accept at once, and any
other owner holds it once its replica copies the CASE_MANAGER's entry.  An
accept before then sends the Accept again, a repeat that changes nothing
(CM-13-005).
"""

import json
import logging
from typing import ClassVar, cast

import py_trees.behaviour

from vultron.core.behaviors.embargo.nodes import (
    EMBARGO_ACTIVATION_SEMANTIC_TYPE,
)
from vultron.core.behaviors.embargo.trigger_tree import (
    accept_embargo_trigger_bt,
    activate_embargo_trigger_bt,
)
from vultron.core.behaviors.sender_entitlement import (
    is_case_owner as _is_case_owner,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.services.embargo_lifecycle import owner_declined_embargo
from vultron.core.use_cases.triggers._base import SvcEmbargoTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    _resolve_embargo_proposal,
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
)
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)


class SvcAcceptEmbargoUseCase(SvcEmbargoTriggerBase):
    _assertion_semantic_type: ClassVar[str] = (
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value
    )

    def _prepare(self) -> None:
        request = cast(AcceptEmbargoTriggerRequest, self._request)
        dl = self._dl

        actor = resolve_actor(request.actor_id, dl)
        self._actor_id = actor.id_
        self._case = resolve_case(request.case_id, dl)
        # An open proposal, or — when named — the actor's received Invite
        # for the embargo in force (EP-09-012).
        self._proposal_id, self._embargo_id = _resolve_embargo_proposal(
            self._case,
            request.proposal_id,
            self._actor_id,
            dl,
            self._received_activities,
        )

        embargo = dl.read(self._embargo_id)
        if embargo is None:
            raise VultronValidationError(
                f"Could not resolve EmbargoEvent '{self._embargo_id}'."
            )
        # A declined owner accepts the invitation first and activates on its
        # next accept: an activation from a DECLINED row is refused
        # (MSM-07-037, ADR-0180).
        self._activates = _is_case_owner(
            self._case, self._actor_id
        ) and not owner_declined_embargo(dl, self._case, self._embargo_id)

    def _asserted_semantic_type(self) -> str:
        if self._activates:
            return EMBARGO_ACTIVATION_SEMANTIC_TYPE
        return self._assertion_semantic_type

    def _assertion_subject(self) -> str:
        return self._proposal_id

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activity(to: list[str] | None) -> tuple[str, str]:
            if self._activates:
                accept_id, accept_blob = self._factory.activate_embargo(
                    embargo_id=self._embargo_id,
                    proposal_id=self._proposal_id,
                    case_id=self._case.id_,
                    actor=self._actor_id,
                    to=to,
                    at=self._at,
                )
            else:
                accept_id, accept_blob = self._factory.accept_embargo(
                    proposal_id=self._proposal_id,
                    case_id=self._case.id_,
                    actor=self._actor_id,
                    to=to,
                    at=self._at,
                )
            self._captured["activity"] = json.loads(accept_blob)
            return accept_id, accept_blob

        build_tree = (
            activate_embargo_trigger_bt
            if self._activates
            else accept_embargo_trigger_bt
        )
        return build_tree(
            case_id=self._case.id_,
            embargo_id=self._embargo_id,
            result_out=self._result_out,
            activity_builder=_build_activity,
        )

    def _log_lifecycle_result(self) -> None:
        lr = self._lifecycle_result
        if self._activates and lr.em_after != lr.em_before:
            logger.info(
                "Actor '%s' accepted embargo proposal '%s'; activated embargo"
                " '%s' on case '%s' (EM %s → %s)",
                self._actor_id,
                self._proposal_id,
                self._embargo_id,
                self._case.id_,
                lr.em_before,
                lr.em_after,
            )
        else:
            logger.info(
                "Actor '%s' accepted embargo proposal '%s'; recorded"
                " participant consent for embargo '%s' on case '%s'"
                " (EM unchanged at %s)",
                self._actor_id,
                self._proposal_id,
                self._embargo_id,
                self._case.id_,
                lr.em_after,
            )
