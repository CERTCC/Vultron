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

from vultron.core.models.status import (
    OfferStatus,
    ReportStatus,
    get_status_layer,
    set_status,
)
from vultron.wire.as2.rehydration import rehydrate
from vultron.core.states.rm import RM
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.report.validate_tree import (
    create_validate_report_tree,
)
from vultron.core.models.status import OfferStatusEnum
from vultron.core.ports.datalayer import DataLayer
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
    VultronConflictError,
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

    try:
        offer = rehydrate(offer_raw, dl=dl)
        report = rehydrate(offer.as_object, dl=dl)
    except (ValueError, KeyError, AttributeError) as e:
        raise VultronValidationError(str(e)) from e

    if getattr(report, "as_type", None) != "VulnerabilityReport":
        raise VultronValidationError(
            f"Expected VulnerabilityReport, got "
            f"{getattr(report, 'as_type', type(report).__name__)}."
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
        actor_id = actor.as_id

        offer, report = _resolve_offer_and_report(offer_id, dl)
        report_id = report.as_id
        offer_id = offer.as_id

        before = outbox_ids(actor)

        bridge = BTBridge(datalayer=dl)
        tree = create_validate_report_tree(
            report_id=report_id, offer_id=offer_id
        )

        context = {}
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
        actor_id = actor.as_id

        offer, report = _resolve_offer_and_report(offer_id, dl)

        invalidate_activity = RmInvalidateReportActivity(
            actor=actor_id,
            object=offer.as_id,
        )

        try:
            dl.create(invalidate_activity)
        except ValueError:
            logger.warning(
                "InvalidateReport activity '%s' already exists",
                invalidate_activity.as_id,
            )

        set_status(
            OfferStatus(
                object_type=offer.as_type,
                object_id=offer.as_id,
                status=OfferStatusEnum.TENTATIVELY_REJECTED,
                actor_id=actor_id,
            )
        )
        set_status(
            ReportStatus(
                object_type=report.as_type,
                object_id=report.as_id,
                status=RM.INVALID,
                actor_id=actor_id,
            )
        )

        add_activity_to_outbox(actor_id, invalidate_activity.as_id, dl)

        logger.info(
            "Actor '%s' invalidated offer '%s' (report '%s')",
            actor_id,
            offer.as_id,
            report.as_id,
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
        actor_id = actor.as_id

        offer, report = _resolve_offer_and_report(offer_id, dl)

        reject_activity = RmCloseReportActivity(
            actor=actor_id,
            object=offer.as_id,
        )

        try:
            dl.create(reject_activity)
        except ValueError:
            logger.warning(
                "CloseReport activity '%s' already exists",
                reject_activity.as_id,
            )

        set_status(
            OfferStatus(
                object_type=offer.as_type,
                object_id=offer.as_id,
                status=OfferStatusEnum.REJECTED,
                actor_id=actor_id,
            )
        )
        set_status(
            ReportStatus(
                object_type=report.as_type,
                object_id=report.as_id,
                status=RM.CLOSED,
                actor_id=actor_id,
            )
        )

        add_activity_to_outbox(actor_id, reject_activity.as_id, dl)

        logger.info(
            "Actor '%s' hard-closed offer '%s' (report '%s'); note: %s",
            actor_id,
            offer.as_id,
            report.as_id,
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
        actor_id = actor.as_id

        offer, report = _resolve_offer_and_report(offer_id, dl)

        status_layer = get_status_layer()
        type_dict = status_layer.get(report.as_type, {})
        id_dict = type_dict.get(report.as_id, {})
        actor_status_dict = id_dict.get(actor_id, {})
        current_rm_state = actor_status_dict.get("status")

        if current_rm_state == RM.CLOSED:
            raise VultronConflictError(
                f"Report '{report.as_id}' is already CLOSED."
            )

        close_activity = RmCloseReportActivity(
            actor=actor_id,
            object=offer.as_id,
        )

        try:
            dl.create(close_activity)
        except ValueError:
            logger.warning(
                "CloseReport activity '%s' already exists",
                close_activity.as_id,
            )

        set_status(
            OfferStatus(
                object_type=offer.as_type,
                object_id=offer.as_id,
                status=OfferStatusEnum.REJECTED,
                actor_id=actor_id,
            )
        )
        set_status(
            ReportStatus(
                object_type=report.as_type,
                object_id=report.as_id,
                status=RM.CLOSED,
                actor_id=actor_id,
            )
        )

        add_activity_to_outbox(actor_id, close_activity.as_id, dl)

        logger.info(
            "Actor '%s' closed offer '%s' (report '%s') via RM lifecycle; note: %s",
            actor_id,
            offer.as_id,
            report.as_id,
            note,
        )

        activity = close_activity.model_dump(by_alias=True, exclude_none=True)
        return {"activity": activity}
