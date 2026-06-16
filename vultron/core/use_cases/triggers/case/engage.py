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

import logging
from typing import cast

import py_trees.behaviour

from vultron.core.behaviors.case.engage_defer_trigger_tree import (
    engage_case_trigger_bt,
)
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import EngageCaseTriggerRequest

logger = logging.getLogger(__name__)


class SvcEngageCaseUseCase(SvcBTTriggerBase):
    """Engage a case (RM → ACCEPTED).

    Updates the actor's RM state to ACCEPTED and sends an Engage(Case)
    activity to the Case Actor via SenderSideBT (PCR-08-001).
    """

    def _prepare(self) -> None:
        request = cast(EngageCaseTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._case_id = resolve_case(request.case_id, self._dl).id_

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activities(case_manager_id: str) -> list[str]:
            activity_id, activity_dict = self._factory.engage_case(
                case_id=self._case_id,
                actor=self._actor_id,
                to=[case_manager_id],
            )
            self._captured["activity"] = activity_dict
            return [activity_id]

        return engage_case_trigger_bt(
            case_id=self._case_id,
            actor_id=self._actor_id,
            activity_builder=_build_activities,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' engaged case '%s' (RM → ACCEPTED)",
            self._actor_id,
            self._case_id,
        )
