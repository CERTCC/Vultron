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
from typing import TYPE_CHECKING, Any

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.create_case_trigger_tree import (
    create_case_trigger_bt,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
)
from vultron.core.use_cases.triggers.requests import (
    CreateCaseTriggerRequest,
)
from vultron.errors import VultronNotFoundError, VultronValidationError

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class SvcCreateCaseUseCase:
    """Create a new VulnerabilityCase and emit a CreateCaseActivity.

    The actor creates a local case and queues the activity for delivery to
    the CaseActor inbox. An optional report_id links an existing
    VulnerabilityReport to the new case.

    BT-15-001 audit: protocol-observable case creation and outbound activity
    emission are delegated to a trigger-side BT.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: CreateCaseTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict[str, Any]:
        actor_id = self._request.actor_id
        actor = resolve_actor(actor_id, self._dl)
        actor_id = actor.id_
        report_id = self._request.report_id

        if report_id is not None:
            raw = self._dl.read(report_id)
            if raw is None:
                raise VultronNotFoundError("VulnerabilityReport", report_id)
            if getattr(raw, "type_", "") != "VulnerabilityReport":
                raise VultronValidationError(
                    f"'{report_id}' is not a VulnerabilityReport"
                )
            report_id = getattr(raw, "id_", None) or report_id

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcCreateCaseUseCase requires a TriggerActivityPort"
            )

        factory = self._trigger_activity
        result_data: dict[str, Any] = {}

        def _build_activity(case_id: str) -> tuple[str, dict[str, Any]]:
            return factory.create_case(case_id=case_id, actor=actor_id)

        bridge = BTBridge(datalayer=self._dl, trigger_activity=factory)
        tree = create_case_trigger_bt(
            case_name=self._request.name,
            case_content=self._request.content,
            report_id=report_id,
            result_out=result_data,
            activity_builder=_build_activity,
        )
        result = bridge.execute_with_setup(tree, actor_id=actor_id)
        if result.status != Status.SUCCESS:
            raise VultronValidationError(
                f"CreateCase failed: {BTBridge.get_failure_reason(tree)}"
            )

        case_id = result_data.get("case_id")
        activity = result_data.get("activity")

        logger.info(
            "Actor '%s' created case '%s' (CreateCaseActivity '%s')",
            actor_id,
            case_id,
            activity.get("id") if isinstance(activity, dict) else None,
        )

        return {"activity": activity}
