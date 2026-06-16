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

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.trigger_tree import (
    propose_embargo_trigger_bt,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.services.embargo_lifecycle import EmbargoLifecycleResult
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    ProposeEmbargoTriggerRequest,
)
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)


class SvcProposeEmbargoUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: ProposeEmbargoTriggerRequest,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._request: ProposeEmbargoTriggerRequest = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        end_time = request.end_time
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        case = resolve_case(case_id, dl)

        embargo_kwargs: dict = {"context": case.id_}
        if end_time is not None:
            embargo_kwargs["end_time"] = end_time

        embargo = EmbargoEvent(**embargo_kwargs)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcProposeEmbargoUseCase requires a TriggerActivityPort"
            )

        factory = self._trigger_activity
        captured: dict = {}
        result_out: dict[str, object] = {}

        def _build_activities(case_manager_id: str) -> list[str]:
            proposal_id, proposal_dict = factory.propose_embargo(
                embargo_id=embargo.id_,
                case_id=case.id_,
                actor=actor_id,
                to=[case_manager_id],
            )
            captured["activity"] = proposal_dict
            return [proposal_id]

        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        tree = propose_embargo_trigger_bt(
            case_id=case.id_,
            embargo=embargo,
            result_out=result_out,
            activity_builder=_build_activities,
        )
        result = bridge.execute_with_setup(tree, actor_id=actor_id)
        if result.status != Status.SUCCESS:
            error = result_out.get("error")
            if isinstance(error, Exception):
                raise error
            raise VultronValidationError(
                f"ProposeEmbargo failed: {BTBridge.get_failure_reason(tree)}"
            )
        lifecycle_result = result_out.get("lifecycle_result")
        if not isinstance(lifecycle_result, EmbargoLifecycleResult):
            raise RuntimeError(
                "ProposeEmbargo did not capture lifecycle result in BT output"
            )

        if lifecycle_result.em_after != lifecycle_result.em_before:
            logger.info(
                "Actor '%s' proposed embargo '%s' on case '%s' (EM %s → %s)",
                actor_id,
                embargo.id_,
                case.id_,
                lifecycle_result.em_before,
                lifecycle_result.em_after,
            )
        else:
            logger.info(
                "Actor '%s' counter-proposed embargo '%s' on case '%s'"
                " (EM %s, no state change)",
                actor_id,
                embargo.id_,
                case.id_,
                lifecycle_result.em_before,
            )

        return {"activity": captured.get("activity")}
