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

"""
Class-based use cases for case-level trigger behaviors.

No HTTP framework imports permitted here.
"""

import logging
from typing import Any, cast

from vultron.core.states.rm import RM
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases._helpers import update_participant_rm_state
from vultron.core.use_cases._helpers import case_addressees
from vultron.core.use_cases.triggers._helpers import (
    add_activity_to_outbox,
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AddReportToCaseTriggerRequest,
    CreateCaseTriggerRequest,
    DeferCaseTriggerRequest,
    EngageCaseTriggerRequest,
)
from vultron.errors import VultronNotFoundError, VultronValidationError
from vultron.wire.as2.vocab.activities.case import (
    AddReportToCaseActivity,
    CreateCaseActivity,
    RmDeferCaseActivity,
    RmEngageCaseActivity,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

logger = logging.getLogger(__name__)


class SvcEngageCaseUseCase:
    """Engage a case (RM → ACCEPTED)."""

    def __init__(
        self, dl: DataLayer, request: EngageCaseTriggerRequest
    ) -> None:
        self._dl = dl
        self._request: EngageCaseTriggerRequest = request

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        case = resolve_case(case_id, dl)

        engage_activity = RmEngageCaseActivity(
            actor=actor_id,
            object_=cast(Any, case),
            to=case_addressees(case, actor_id) or None,
        )

        try:
            dl.create(engage_activity)
        except ValueError:
            logger.warning(
                "EngageCase activity '%s' already exists",
                engage_activity.id_,
            )

        update_participant_rm_state(case.id_, actor_id, RM.ACCEPTED, dl)

        add_activity_to_outbox(actor_id, engage_activity.id_, dl)

        logger.info(
            "Actor '%s' engaged case '%s' (RM → ACCEPTED)",
            actor_id,
            case.id_,
        )

        activity = engage_activity.model_dump(by_alias=True, exclude_none=True)
        return {"activity": activity}


class SvcDeferCaseUseCase:
    """Defer a case (RM → DEFERRED)."""

    def __init__(
        self, dl: DataLayer, request: DeferCaseTriggerRequest
    ) -> None:
        self._dl = dl
        self._request: DeferCaseTriggerRequest = request

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        case = resolve_case(case_id, dl)

        defer_activity = RmDeferCaseActivity(
            actor=actor_id,
            object_=cast(Any, case),
            to=case_addressees(case, actor_id) or None,
        )

        try:
            dl.create(defer_activity)
        except ValueError:
            logger.warning(
                "DeferCase activity '%s' already exists",
                defer_activity.id_,
            )

        update_participant_rm_state(case.id_, actor_id, RM.DEFERRED, dl)

        add_activity_to_outbox(actor_id, defer_activity.id_, dl)

        logger.info(
            "Actor '%s' deferred case '%s' (RM → DEFERRED)",
            actor_id,
            case.id_,
        )

        activity = defer_activity.model_dump(by_alias=True, exclude_none=True)
        return {"activity": activity}


class SvcCreateCaseUseCase:
    """Create a new VulnerabilityCase and emit a CreateCaseActivity.

    The actor creates a local case and queues the activity for delivery to
    the CaseActor inbox.  An optional report_id links an existing
    VulnerabilityReport to the new case.
    """

    def __init__(
        self, dl: DataLayer, request: CreateCaseTriggerRequest
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> dict[str, Any]:
        actor_id = self._request.actor_id
        actor = resolve_actor(actor_id, self._dl)

        case = VulnerabilityCase(
            name=self._request.name,
            content=self._request.content,
            attributed_to=actor.id_,
        )

        if self._request.report_id is not None:
            raw = self._dl.read(self._request.report_id)
            if raw is None:
                raise VultronNotFoundError(
                    "VulnerabilityReport", self._request.report_id
                )
            if not isinstance(raw, VulnerabilityReport):
                raise VultronValidationError(
                    f"'{self._request.report_id}' is not a VulnerabilityReport"
                )
            case.vulnerability_reports.append(raw.id_)

        self._dl.create(case)

        activity = CreateCaseActivity(
            actor=actor.id_,
            object_=case,
        )
        self._dl.create(activity)

        add_activity_to_outbox(actor_id, activity.id_, self._dl)

        logger.info(
            "Actor '%s' created case '%s' (CreateCaseActivity '%s')",
            actor_id,
            case.id_,
            activity.id_,
        )

        return {
            "activity": activity.model_dump(by_alias=True, exclude_none=True)
        }


class SvcAddReportToCaseUseCase:
    """Link a VulnerabilityReport to an existing case.

    Emits an AddReportToCaseActivity queued in the actor's outbox.
    """

    def __init__(
        self, dl: DataLayer, request: AddReportToCaseTriggerRequest
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> dict[str, Any]:
        actor_id = self._request.actor_id
        actor = resolve_actor(actor_id, self._dl)
        case = resolve_case(self._request.case_id, self._dl)

        raw = self._dl.read(self._request.report_id)
        if raw is None:
            raise VultronNotFoundError(
                "VulnerabilityReport", self._request.report_id
            )
        if not isinstance(raw, VulnerabilityReport):
            raise VultronValidationError(
                f"'{self._request.report_id}' is not a VulnerabilityReport"
            )
        report = cast(VulnerabilityReport, raw)

        activity = AddReportToCaseActivity(
            actor=actor.id_,
            object_=report,
            target=cast(VulnerabilityCase, case),
        )
        self._dl.create(activity)

        add_activity_to_outbox(actor_id, activity.id_, self._dl)

        logger.info(
            "Actor '%s' added report '%s' to case '%s'",
            actor_id,
            report.id_,
            case.id_,
        )

        return {
            "activity": activity.model_dump(by_alias=True, exclude_none=True)
        }
