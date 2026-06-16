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

"""Embargo proposal trigger use case."""

import logging
from typing import cast

import py_trees.behaviour

from vultron.core.behaviors.embargo.trigger_tree import (
    propose_embargo_trigger_bt,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.use_cases.triggers._base import SvcEmbargoTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    ProposeEmbargoTriggerRequest,
)

logger = logging.getLogger(__name__)


class SvcProposeEmbargoUseCase(SvcEmbargoTriggerBase):
    def _prepare(self) -> None:
        request = cast(ProposeEmbargoTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._case = resolve_case(request.case_id, self._dl)

        embargo_kwargs: dict = {"context": self._case.id_}
        if request.end_time is not None:
            embargo_kwargs["end_time"] = request.end_time
        self._embargo = EmbargoEvent(**embargo_kwargs)

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activities(case_manager_id: str) -> list[str]:
            proposal_id, proposal_dict = self._factory.propose_embargo(
                embargo_id=self._embargo.id_,
                case_id=self._case.id_,
                actor=self._actor_id,
                to=[case_manager_id],
            )
            self._captured["activity"] = proposal_dict
            return [proposal_id]

        return propose_embargo_trigger_bt(
            case_id=self._case.id_,
            embargo=self._embargo,
            result_out=self._result_out,
            activity_builder=_build_activities,
        )

    def _log_lifecycle_result(self) -> None:
        lr = self._lifecycle_result
        if lr.em_after != lr.em_before:
            logger.info(
                "Actor '%s' proposed embargo '%s' on case '%s' (EM %s → %s)",
                self._actor_id,
                self._embargo.id_,
                self._case.id_,
                lr.em_before,
                lr.em_after,
            )
        else:
            logger.info(
                "Actor '%s' counter-proposed embargo '%s' on case '%s'"
                " (EM %s, no state change)",
                self._actor_id,
                self._embargo.id_,
                self._case.id_,
                lr.em_before,
            )
