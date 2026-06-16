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

"""Embargo termination trigger use case."""

import logging

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.trigger_tree import (
    terminate_embargo_trigger_bt,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.services.embargo_lifecycle import EmbargoLifecycleResult
from vultron.core.use_cases.triggers._helpers import (
    _coerce_embargo_event,
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    TerminateEmbargoTriggerRequest,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)

logger = logging.getLogger(__name__)


class SvcTerminateEmbargoUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: TerminateEmbargoTriggerRequest,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._request: TerminateEmbargoTriggerRequest = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        case = resolve_case(case_id, dl)

        if case.active_embargo is None:
            logger.warning(
                "Invalid EM state transition: actor '%s' cannot TERMINATE:"
                " case '%s' has no active embargo.",
                actor_id,
                case.id_,
            )
            raise VultronInvalidStateTransitionError(
                f"Case '{case.id_}' has no active embargo to terminate."
            )

        embargo_id = (
            case.active_embargo
            if isinstance(case.active_embargo, str)
            else getattr(case.active_embargo, "id_", None)
        )
        if embargo_id is None:
            raise VultronValidationError(
                f"Active embargo on case '{case.id_}' is missing an ID."
            )

        _coerce_embargo_event(dl.read(embargo_id), embargo_id)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcTerminateEmbargoUseCase requires a TriggerActivityPort"
            )

        factory = self._trigger_activity
        captured: dict = {}
        result_out: dict[str, object] = {}

        def _build_activities(case_manager_id: str) -> list[str]:
            announce_id, announce_dict = factory.terminate_embargo(
                embargo_id=embargo_id,
                case_id=case.id_,
                actor=actor_id,
                to=[case_manager_id],
            )
            captured["activity"] = announce_dict
            return [announce_id]

        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        tree = terminate_embargo_trigger_bt(
            case_id=case.id_,
            result_out=result_out,
            activity_builder=_build_activities,
        )
        result = bridge.execute_with_setup(tree, actor_id=actor_id)
        if result.status != Status.SUCCESS:
            error = result_out.get("error")
            if isinstance(error, Exception):
                raise error
            raise VultronValidationError(
                f"TerminateEmbargo failed: {BTBridge.get_failure_reason(tree)}"
            )
        lifecycle_result = result_out.get("lifecycle_result")
        if not isinstance(lifecycle_result, EmbargoLifecycleResult):
            raise RuntimeError(
                "TerminateEmbargo did not capture lifecycle result in BT output"
            )

        logger.info(
            "Actor '%s' terminated embargo '%s' on case '%s' (EM %s → %s)",
            actor_id,
            embargo_id,
            case.id_,
            lifecycle_result.em_before,
            lifecycle_result.em_after,
        )

        return {"activity": captured.get("activity")}
