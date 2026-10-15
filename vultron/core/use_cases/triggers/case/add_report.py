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

from typing import cast

from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.case.add_object import (
    SvcAddObjectToCaseUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AddReportToCaseTriggerRequest,
)
from vultron.errors import VultronNotFoundError, VultronValidationError


class SvcAddReportToCaseUseCase(SvcAddObjectToCaseUseCase):
    """Link a VulnerabilityReport to an existing case.

    Validates that the referenced object is a ``VulnerabilityReport``, then
    delegates to :class:`SvcAddObjectToCaseUseCase` (TRIG-10-002), which
    sends ``Add(VulnerabilityReport, target=VulnerabilityCase)`` to the
    CASE_MANAGER alone (PCR-08-005) and records the pending assertion.
    """

    def _prepare(self) -> None:
        request = cast(AddReportToCaseTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._case_id = resolve_case(request.case_id, self._dl).id_
        self._object_id = request.report_id
        raw = self._dl.read(self._object_id)
        if raw is None:
            raise VultronNotFoundError("VulnerabilityReport", self._object_id)
        if getattr(raw, "type_", "") != "VulnerabilityReport":
            raise VultronValidationError(
                f"'{self._object_id}' is not a VulnerabilityReport"
            )
