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
Class-based use cases for report-level trigger behaviors.

Each class accepts a ``DataLayer`` and ``request`` at construction time and
exposes a single ``execute()`` method.  Helper function
``_resolve_offer_and_report`` is kept at module level because it may be
shared by multiple classes.

No HTTP framework imports (FastAPI, Starlette) are permitted here.
"""

import logging
from typing import Any

from vultron.wire.as2.rehydration import rehydrate
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.core.states.rm import RM
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.report.validate_tree import (
    create_validate_report_tree,
)
from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases._helpers import (
    _idempotent_create,
    _report_phase_status_id,
)
from vultron.core.use_cases.triggers._helpers import (
    add_activity_to_outbox,
    outbox_ids,
    resolve_actor,
)
from vultron.core.use_cases.triggers.requests import (
    CloseReportTriggerRequest,
    InvalidateReportTriggerRequest,
    RejectReportTriggerRequest,
    ValidateReportTriggerRequest,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.activities.report import (
    RmCloseReportActivity,
    RmInvalidateReportActivity,
)

logger = logging.getLogger(__name__)


def _resolve_offer_and_report(offer_id: str, dl: DataLayer):
    """Resolve offer and its embedded report; raise domain errors on failure."""
    offer_raw = dl.read(offer_id)
    if offer_raw is None:
        raise VultronNotFoundError("Offer", offer_id)
    if not isinstance(offer_raw, as_Object):
        raise VultronValidationError(
            f"Expected AS2 object for offer, got {type(offer_raw).__name__}."
        )

    try:
        offer = rehydrate(offer_raw, dl=dl)
        offer_object = getattr(offer, "object_", None)
        if offer_object is None:
            raise VultronValidationError("Offer is missing object reference.")
        report = rehydrate(offer_object, dl=dl)
    except (ValueError, KeyError, AttributeError) as e:
        raise VultronValidationError(str(e)) from e

    if getattr(report, "type_", None) != "VulnerabilityReport":
        raise VultronValidationError(
            f"Expected VulnerabilityReport, got "
            f"{getattr(report, 'type_', type(report).__name__)}."
        )

    return offer, report


class SvcValidateReportUseCase:
    """Validate a report offer using the ValidateReportBT behavior tree."""

    def __init__(
        self, dl: DataLayer, request: ValidateReportTriggerRequest
    ) -> None:
        self._dl = dl
        self._request: ValidateReportTriggerRequest = request

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        offer_id = request.offer_id
        note = request.note
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        offer, report = _resolve_offer_and_report(offer_id, dl)
        report_id = report.id_
        offer_id = offer.id_

        before = outbox_ids(actor)

        bridge = BTBridge(datalayer=dl)
        tree = create_validate_report_tree(
            report_id=report_id, offer_id=offer_id
        )

        context: dict[str, Any] = {}
        if note:
            context["note"] = note

        bridge.execute_with_setup(tree, actor_id=actor_id, **context)

        activity = None
        actor_after = dl.read(actor_id)
        if actor_after is not None:
            after = outbox_ids(actor_after)
            new_items = after - before
            if new_items:
                activity_id = next(iter(new_items))
                activity_obj = dl.read(activity_id)
                if activity_obj is not None:
                    activity = activity_obj.model_dump(
                        by_alias=True, exclude_none=True
                    )

        return {"activity": activity}


class SvcInvalidateReportUseCase:
    """Emit RmInvalidateReportActivity (TentativeReject) for the given offer."""

    def __init__(
        self, dl: DataLayer, request: InvalidateReportTriggerRequest
    ) -> None:
        self._dl = dl
        self._request: InvalidateReportTriggerRequest = request

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        offer_id = request.offer_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        offer, report = _resolve_offer_and_report(offer_id, dl)

        invalidate_activity = RmInvalidateReportActivity(
            actor=actor_id,
            object_=offer.id_,
        )

        try:
            dl.create(invalidate_activity)
        except ValueError:
            logger.warning(
                "InvalidateReport activity '%s' already exists",
                invalidate_activity.id_,
            )

        set_status_invalidate = VultronParticipantStatus(
            id_=_report_phase_status_id(
                actor_id, report.id_, RM.INVALID.value
            ),
            context=report.id_,
            attributed_to=actor_id,
            rm_state=RM.INVALID,
        )
        _idempotent_create(
            dl,
            "ParticipantStatus",
            set_status_invalidate.id_,
            set_status_invalidate,
            "ParticipantStatus (report-phase RM.INVALID)",
        )

        add_activity_to_outbox(actor_id, invalidate_activity.id_, dl)

        logger.info(
            "Actor '%s' invalidated offer '%s' (report '%s')",
            actor_id,
            offer.id_,
            report.id_,
        )

        activity = invalidate_activity.model_dump(
            by_alias=True, exclude_none=True
        )
        return {"activity": activity}


class SvcRejectReportUseCase:
    """Hard-close a report offer by emitting RmCloseReportActivity (Reject)."""

    def __init__(
        self, dl: DataLayer, request: RejectReportTriggerRequest
    ) -> None:
        self._dl = dl
        self._request: RejectReportTriggerRequest = request

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        offer_id = request.offer_id
        note = request.note
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        offer, report = _resolve_offer_and_report(offer_id, dl)

        reject_activity = RmCloseReportActivity(
            actor=actor_id,
            object_=offer.id_,
        )

        try:
            dl.create(reject_activity)
        except ValueError:
            logger.warning(
                "CloseReport activity '%s' already exists",
                reject_activity.id_,
            )

        set_status_reject = VultronParticipantStatus(
            id_=_report_phase_status_id(actor_id, report.id_, RM.CLOSED.value),
            context=report.id_,
            attributed_to=actor_id,
            rm_state=RM.CLOSED,
        )
        _idempotent_create(
            dl,
            "ParticipantStatus",
            set_status_reject.id_,
            set_status_reject,
            "ParticipantStatus (report-phase RM.CLOSED)",
        )

        add_activity_to_outbox(actor_id, reject_activity.id_, dl)

        logger.info(
            "Actor '%s' hard-closed offer '%s' (report '%s'); note: %s",
            actor_id,
            offer.id_,
            report.id_,
            note,
        )

        activity = reject_activity.model_dump(by_alias=True, exclude_none=True)
        return {"activity": activity}


class SvcCloseReportUseCase:
    """Close a report via the RM lifecycle (RM → C transition)."""

    def __init__(
        self, dl: DataLayer, request: CloseReportTriggerRequest
    ) -> None:
        self._dl = dl
        self._request: CloseReportTriggerRequest = request

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        offer_id = request.offer_id
        note = request.note
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        offer, report = _resolve_offer_and_report(offer_id, dl)

        closed_id = _report_phase_status_id(
            actor_id, report.id_, RM.CLOSED.value
        )
        if dl.get("ParticipantStatus", closed_id) is not None:
            logger.warning(
                "Invalid RM state transition: report '%s' is already CLOSED.",
                report.id_,
            )
            raise VultronInvalidStateTransitionError(
                f"Report '{report.id_}' is already CLOSED."
            )

        close_activity = RmCloseReportActivity(
            actor=actor_id,
            object_=offer.id_,
        )

        try:
            dl.create(close_activity)
        except ValueError:
            logger.warning(
                "CloseReport activity '%s' already exists",
                close_activity.id_,
            )

        set_status_close = VultronParticipantStatus(
            id_=closed_id,
            context=report.id_,
            attributed_to=actor_id,
            rm_state=RM.CLOSED,
        )
        _idempotent_create(
            dl,
            "ParticipantStatus",
            set_status_close.id_,
            set_status_close,
            "ParticipantStatus (report-phase RM.CLOSED)",
        )

        add_activity_to_outbox(actor_id, close_activity.id_, dl)

        logger.info(
            "Actor '%s' closed offer '%s' (report '%s') via RM lifecycle; note: %s",
            actor_id,
            offer.id_,
            report.id_,
            note,
        )

        activity = close_activity.model_dump(by_alias=True, exclude_none=True)
        return {"activity": activity}
