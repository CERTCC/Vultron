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
from typing import TYPE_CHECKING

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.engage_defer_trigger_tree import (
    engage_case_trigger_bt,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    EngageCaseTriggerRequest,
)
from vultron.errors import VultronValidationError

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class SvcEngageCaseUseCase:
    """Engage a case (RM → ACCEPTED).

    Updates the actor's RM state to ACCEPTED and sends an Engage(Case)
    activity to the Case Actor via SenderSideBT (PCR-08-001).
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: EngageCaseTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: EngageCaseTriggerRequest = request
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
                "SvcEngageCaseUseCase requires a TriggerActivityPort"
            )

        factory = self._trigger_activity
        captured: dict = {}

        def _build_activities(case_manager_id: str) -> list[str]:
            activity_id, activity_dict = factory.engage_case(
                case_id=case_id,
                actor=actor_id,
                to=[case_manager_id],
            )
            captured["activity"] = activity_dict
            return [activity_id]

        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        tree = engage_case_trigger_bt(
            case_id=case_id,
            actor_id=actor_id,
            activity_builder=_build_activities,
        )
        result = bridge.execute_with_setup(tree, actor_id=actor_id)

        if result.status != Status.SUCCESS:
            raise VultronValidationError(
                f"EngageCase failed: {BTBridge.get_failure_reason(tree)}"
            )

        logger.info(
            "Actor '%s' engaged case '%s' (RM → ACCEPTED)",
            actor_id,
            case_id,
        )

        return {"activity": captured.get("activity")}
