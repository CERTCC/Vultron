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
from typing import Any, cast

import py_trees.behaviour

from vultron.core.behaviors.case.add_object_trigger_tree import (
    add_object_trigger_bt,
)
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AddReportToCaseTriggerRequest,
)
from vultron.errors import VultronNotFoundError, VultronValidationError

logger = logging.getLogger(__name__)


class SvcAddReportToCaseUseCase(SvcBTTriggerBase):
    """Link a VulnerabilityReport to an existing case.

    Validates that the referenced object is a ``VulnerabilityReport``, then
    delegates to the same Add-object BT as ``SvcAddObjectToCaseUseCase``
    (TRIG-10-002).
    Emits an ``Add(VulnerabilityReport, target=VulnerabilityCase)`` activity
    queued in the actor's outbox.

    BT-15-001 audit: outbound Add(Report,target=case) emission and outbox
    queueing are delegated to a trigger-side BT.
    """

    def _prepare(self) -> None:
        request = cast(AddReportToCaseTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._case_id = resolve_case(request.case_id, self._dl).id_
        self._object_id: str = request.report_id
        raw = self._dl.read(self._object_id)
        if raw is None:
            raise VultronNotFoundError("VulnerabilityReport", self._object_id)
        if getattr(raw, "type_", "") != "VulnerabilityReport":
            raise VultronValidationError(
                f"'{self._object_id}' is not a VulnerabilityReport"
            )

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activity() -> tuple[str, dict[str, Any]]:
            return self._factory.add_object_to_case(
                actor=self._actor_id,
                object_id=self._object_id,
                case_id=self._case_id,
            )

        return add_object_trigger_bt(
            result_out=self._result_out,
            activity_builder=_build_activity,
        )

    def _extra_execute_kwargs(self) -> dict[str, Any]:
        return {"case_id": self._case_id}

    def _handle_result(self) -> None:
        self._captured["activity"] = self._result_out.get("activity")
        logger.info(
            "Actor '%s' added object '%s' to case '%s'",
            self._actor_id,
            self._object_id,
            self._case_id,
        )
