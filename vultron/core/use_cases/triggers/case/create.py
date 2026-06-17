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

from vultron.core.behaviors.case.create_case_trigger_tree import (
    create_case_trigger_bt,
)
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers._helpers import resolve_actor
from vultron.core.use_cases.triggers.requests import CreateCaseTriggerRequest
from vultron.errors import VultronNotFoundError, VultronValidationError

logger = logging.getLogger(__name__)


class SvcCreateCaseUseCase(SvcBTTriggerBase):
    """Create a new VulnerabilityCase and emit a CreateCaseActivity.

    The actor creates a local case and queues the activity for delivery to
    the CaseActor inbox. An optional report_id links an existing
    VulnerabilityReport to the new case.

    BT-15-001 audit: protocol-observable case creation and outbound activity
    emission are delegated to a trigger-side BT.
    """

    def _prepare(self) -> None:
        request = cast(CreateCaseTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._case_name: str = request.name
        self._case_content: str = request.content

        report_id = request.report_id
        if report_id is not None:
            raw = self._dl.read(report_id)
            if raw is None:
                raise VultronNotFoundError("VulnerabilityReport", report_id)
            if getattr(raw, "type_", "") != "VulnerabilityReport":
                raise VultronValidationError(
                    f"'{report_id}' is not a VulnerabilityReport"
                )
            report_id = getattr(raw, "id_", None) or report_id
        self._report_id: str | None = report_id

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activity(case_id: str) -> tuple[str, dict[str, Any]]:
            return self._factory.create_case(
                case_id=case_id, actor=self._actor_id
            )

        return create_case_trigger_bt(
            case_name=self._case_name,
            case_content=self._case_content,
            report_id=self._report_id,
            result_out=self._result_out,
            activity_builder=_build_activity,
        )

    def _handle_result(self) -> None:
        self._captured["activity"] = self._result_out.get("activity")
        activity = self._captured.get("activity")
        logger.info(
            "Actor '%s' created case '%s' (CreateCaseActivity '%s')",
            self._actor_id,
            self._result_out.get("case_id"),
            activity.get("id") if isinstance(activity, dict) else None,
        )
