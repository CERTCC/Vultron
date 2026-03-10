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
Domain service functions for report-level trigger behaviors.

Each function accepts domain parameters and a DataLayer instance (injected
from the router via Depends).  No HTTP routing or request parsing belongs
here.
"""

import logging

from fastapi import HTTPException, status

from vultron.api.v2.backend.trigger_services._helpers import (
    add_activity_to_outbox,
    not_found,
    outbox_ids,
    resolve_actor,
)
from vultron.api.v2.data.rehydration import rehydrate
from vultron.api.v2.data.status import (
    OfferStatus,
    ReportStatus,
    get_status_layer,
    set_status,
)
from vultron.api.v2.datalayer.abc import DataLayer
from vultron.wire.as2.vocab.activities.report import (
    RmCloseReport,
    RmInvalidateReport,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.report.validate_tree import (
    create_validate_report_tree,
)
from vultron.bt.report_management.states import RM
from vultron.enums import OfferStatusEnum

logger = logging.getLogger(__name__)


def _resolve_offer_and_report(offer_id: str, dl: DataLayer):
    """Resolve offer and its embedded report; raise 404/422 on failure."""
    offer_raw = dl.read(offer_id)
    if offer_raw is None:
        raise not_found("Offer", offer_id)

    try:
        offer = rehydrate(offer_raw)
        report = rehydrate(offer.as_object)
    except (ValueError, KeyError, AttributeError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": 422,
                "error": "ValidationError",
                "message": str(e),
                "activity_id": None,
            },
        )

    if getattr(report, "as_type", None) != "VulnerabilityReport":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": 422,
                "error": "ValidationError",
                "message": (
                    f"Expected VulnerabilityReport, got "
                    f"{getattr(report, 'as_type', type(report).__name__)}."
                ),
                "activity_id": None,
            },
        )

    return offer, report


def svc_validate_report(
    actor_id: str, offer_id: str, note: str | None, dl: DataLayer
) -> dict:
    """
    Validate a report offer using the ValidateReportBT behavior tree.

    Resolves the actor and offer, invokes the ValidateReportBT tree via the
    bridge layer, and returns {"activity": {...}} with the resulting activity.

    Implements: TB-01-001, TB-01-002, TB-01-003, TB-03-001, TB-03-002,
        TB-03-003, TB-04-001, TB-05-001, TB-05-002, TB-06-001, TB-06-002,
        TB-07-001
    """
    actor = resolve_actor(actor_id, dl)
    actor_id = actor.as_id

    offer, report = _resolve_offer_and_report(offer_id, dl)
    report_id = report.as_id
    offer_id = offer.as_id

    before = outbox_ids(actor)

    bridge = BTBridge(datalayer=dl)
    tree = create_validate_report_tree(report_id=report_id, offer_id=offer_id)

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


def svc_invalidate_report(
    actor_id: str, offer_id: str, note: str | None, dl: DataLayer
) -> dict:
    """
    Emit RmInvalidateReport (TentativeReject) for the given offer.

    Updates offer status to TENTATIVELY_REJECTED and report status to INVALID.

    Implements: TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001,
        TB-03-002, TB-03-003, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    actor = resolve_actor(actor_id, dl)
    actor_id = actor.as_id

    offer, report = _resolve_offer_and_report(offer_id, dl)

    invalidate_activity = RmInvalidateReport(
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

    activity = invalidate_activity.model_dump(by_alias=True, exclude_none=True)
    return {"activity": activity}


def svc_reject_report(
    actor_id: str, offer_id: str, note: str, dl: DataLayer
) -> dict:
    """
    Hard-close a report offer by emitting RmCloseReport (Reject).

    Updates offer status to REJECTED and report status to CLOSED.

    Implements: TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001,
        TB-03-002, TB-03-004, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    actor = resolve_actor(actor_id, dl)
    actor_id = actor.as_id

    offer, report = _resolve_offer_and_report(offer_id, dl)

    reject_activity = RmCloseReport(
        actor=actor_id,
        object=offer.as_id,
    )

    try:
        dl.create(reject_activity)
    except ValueError:
        logger.warning(
            "CloseReport activity '%s' already exists", reject_activity.as_id
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


def svc_close_report(
    actor_id: str, offer_id: str, note: str | None, dl: DataLayer
) -> dict:
    """
    Close a report via the RM lifecycle (RM → C transition).

    Emits RmCloseReport (Reject).  Returns 409 if report is already CLOSED.
    Updates offer status to REJECTED and report status to CLOSED.

    Distinction from reject_report: close_report closes a report that has
    already progressed through the RM lifecycle (RM → C), while reject_report
    hard-rejects an incoming offer before validation completes.

    Implements: TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001,
        TB-03-002, TB-03-003, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    actor = resolve_actor(actor_id, dl)
    actor_id = actor.as_id

    offer, report = _resolve_offer_and_report(offer_id, dl)

    status_layer = get_status_layer()
    type_dict = status_layer.get(report.as_type, {})
    id_dict = type_dict.get(report.as_id, {})
    actor_status_dict = id_dict.get(actor_id, {})
    current_rm_state = actor_status_dict.get("status")

    if current_rm_state == RM.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "status": 409,
                "error": "Conflict",
                "message": (f"Report '{report.as_id}' is already CLOSED."),
                "activity_id": None,
            },
        )

    close_activity = RmCloseReport(
        actor=actor_id,
        object=offer.as_id,
    )

    try:
        dl.create(close_activity)
    except ValueError:
        logger.warning(
            "CloseReport activity '%s' already exists", close_activity.as_id
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
