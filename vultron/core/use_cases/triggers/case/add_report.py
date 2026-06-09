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

from typing import TYPE_CHECKING, Any

from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases.triggers.requests import (
    AddObjectToCaseTriggerRequest,
    AddReportToCaseTriggerRequest,
)
from vultron.errors import VultronNotFoundError, VultronValidationError

from .add_object import SvcAddObjectToCaseUseCase

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort


class SvcAddReportToCaseUseCase:
    """Link a VulnerabilityReport to an existing case.

    Validates that the referenced object is a ``VulnerabilityReport``, then
    delegates to :class:`SvcAddObjectToCaseUseCase` (TRIG-10-002).
    Emits an ``Add(VulnerabilityReport, target=VulnerabilityCase)`` activity
    queued in the actor's outbox.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddReportToCaseTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict[str, Any]:
        actor_id = self._request.actor_id
        dl = self._dl

        raw = dl.read(self._request.report_id)
        if raw is None:
            raise VultronNotFoundError(
                "VulnerabilityReport", self._request.report_id
            )
        if getattr(raw, "type_", "") != "VulnerabilityReport":
            raise VultronValidationError(
                f"'{self._request.report_id}' is not a VulnerabilityReport"
            )

        inner = SvcAddObjectToCaseUseCase(
            dl,
            AddObjectToCaseTriggerRequest(
                actor_id=actor_id,
                case_id=self._request.case_id,
                object_id=self._request.report_id,
            ),
            trigger_activity=self._trigger_activity,
        )
        return inner.execute()
