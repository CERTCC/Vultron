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

"""Embargo rejection trigger use case."""

import json
import logging
from typing import ClassVar, cast

import py_trees.behaviour

from vultron.core.behaviors.embargo.trigger_tree import (
    reject_embargo_trigger_bt,
)
from vultron.core.behaviors.sender_entitlement import (
    is_case_owner as _is_case_owner,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.use_cases.triggers._base import SvcEmbargoTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    _resolve_embargo_id_from_proposal_id,
    _resolve_embargo_proposal,
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    RejectEmbargoTriggerRequest,
)

logger = logging.getLogger(__name__)


class SvcRejectEmbargoUseCase(SvcEmbargoTriggerBase):
    _assertion_event_type: ClassVar[str] = (
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value
    )

    def _prepare(self) -> None:
        request = cast(RejectEmbargoTriggerRequest, self._request)
        dl = self._dl

        actor = resolve_actor(request.actor_id, dl)
        self._actor_id = actor.id_
        self._case = resolve_case(request.case_id, dl)
        self._proposal_id = _resolve_embargo_proposal(
            self._case, request.proposal_id, dl
        )
        self._embargo_id = _resolve_embargo_id_from_proposal_id(
            self._case, self._proposal_id
        )

    def _assertion_subject(self) -> str:
        return self._proposal_id

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activity(to: list[str] | None) -> tuple[str, str]:
            reject_id, reject_blob = self._factory.reject_embargo(
                proposal_id=self._proposal_id,
                case_id=self._case.id_,
                actor=self._actor_id,
                to=to,
            )
            self._captured["activity"] = json.loads(reject_blob)
            return reject_id, reject_blob

        return reject_embargo_trigger_bt(
            case_id=self._case.id_,
            embargo_id=self._embargo_id,
            result_out=self._result_out,
            activity_builder=_build_activity,
        )

    def _log_lifecycle_result(self) -> None:
        lr = self._lifecycle_result
        if (
            _is_case_owner(self._case, self._actor_id)
            and lr.em_after != lr.em_before
        ):
            logger.info(
                "Actor '%s' rejected embargo proposal '%s' on case '%s'"
                " (EM %s → %s)",
                self._actor_id,
                self._proposal_id,
                self._case.id_,
                lr.em_before,
                lr.em_after,
            )
        else:
            logger.info(
                "Actor '%s' rejected embargo proposal '%s'; recorded"
                " participant consent for embargo '%s' on case '%s'"
                " (EM unchanged at %s)",
                self._actor_id,
                self._proposal_id,
                self._embargo_id,
                self._case.id_,
                lr.em_after,
            )
