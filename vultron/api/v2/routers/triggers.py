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
Trigger endpoints for actor-initiated Vultron behaviors.

Implements POST /actors/{actor_id}/trigger/{behavior-name} for behaviors
a local actor initiates based on their own state rather than reacting to
an inbound message (the outgoing counterpart to the inbound handler pipeline).

Per specs/triggerable-behaviors.md (TRG prefix) TB-01 through TB-07.
Per notes/triggerable-behaviors.md design notes.

Naming convention (per notes/triggerable-behaviors.md §4):
  trigger_* — local actor decides to initiate a behavior (outbound)
  handle_*  — processes an inbound message (reactive, in handlers/)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from vultron.api.v2.data.rehydration import rehydrate
from vultron.api.v2.datalayer.abc import DataLayer
from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.behaviors.bridge import BTBridge
from vultron.behaviors.report.validate_tree import create_validate_report_tree

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/actors", tags=["Triggers"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ValidateReportRequest(BaseModel):
    """
    Request body for the validate-report trigger endpoint.

    TB-03-001: Must include offer_id to identify the target offer.
    TB-03-002: Unknown fields are silently ignored (extra="ignore").
    TB-03-003: Optional note field may be included.
    """

    model_config = ConfigDict(extra="ignore")

    offer_id: str
    note: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _not_found(resource_type: str, resource_id: str) -> HTTPException:
    """Return a structured 404 per EH-05-001."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "status": 404,
            "error": "NotFound",
            "message": f"{resource_type} '{resource_id}' not found.",
            "activity_id": None,
        },
    )


def _resolve_actor(actor_id: str, dl: DataLayer):
    """Resolve actor by full ID or short ID; raise 404 if absent."""
    actor = dl.read(actor_id)
    if actor is None:
        actor = dl.find_actor_by_short_id(actor_id)
    if actor is None:
        raise _not_found("Actor", actor_id)
    return actor


def _outbox_ids(actor) -> set[str]:
    """Return the set of string activity IDs in actor.outbox.items."""
    if not (hasattr(actor, "outbox") and actor.outbox and actor.outbox.items):
        return set()
    return {item for item in actor.outbox.items if isinstance(item, str)}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{actor_id}/trigger/validate-report",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger report validation.",
    description=(
        "Triggers the validate-report behavior for the given actor. "
        "Invokes the ValidateReportBT tree via the bridge layer and "
        "returns the resulting ActivityStreams activity (TB-04-001)."
    ),
)
def trigger_validate_report(
    actor_id: str,
    body: ValidateReportRequest,
    dl: DataLayer = Depends(get_datalayer),
) -> dict:
    """
    Trigger the validate-report behavior for the given actor.

    Resolves the actor and offer, invokes the ValidateReportBT tree via
    the bridge layer, and returns HTTP 202 with the resulting activity.

    Trigger processing is synchronous: BT execution completes before the
    response is returned, so the response body includes the resulting
    activity directly (per notes/triggerable-behaviors.md and TB-04-001).

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-03-001, TB-03-002, TB-03-003,
        TB-04-001, TB-05-001, TB-05-002, TB-06-001, TB-06-002, TB-07-001
    """
    # TB-01-003: Resolve actor or return structured 404
    actor = _resolve_actor(actor_id, dl)
    actor_id = actor.as_id

    # TB-01-003: Resolve offer or return structured 404
    offer_raw = dl.read(body.offer_id)
    if offer_raw is None:
        raise _not_found("Offer", body.offer_id)

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

    if not isinstance(report, VulnerabilityReport):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": 422,
                "error": "ValidationError",
                "message": (
                    f"Expected VulnerabilityReport, got "
                    f"{type(report).__name__}."
                ),
                "activity_id": None,
            },
        )

    report_id = report.as_id
    offer_id = offer.as_id

    # Snapshot outbox before execution to detect new activities (TB-07-001)
    outbox_before = _outbox_ids(actor)

    # TB-05-001, TB-05-002: Invoke BT via bridge layer
    bridge = BTBridge(datalayer=dl)
    tree = create_validate_report_tree(report_id=report_id, offer_id=offer_id)

    context = {}
    if body.note:
        context["note"] = body.note

    bridge.execute_with_setup(tree, actor_id=actor_id, **context)

    # TB-07-001: BT adds resulting activity to actor's outbox; retrieve it
    activity = None
    actor_after = dl.read(actor_id)
    if actor_after is not None:
        outbox_after = _outbox_ids(actor_after)
        new_items = outbox_after - outbox_before
        if new_items:
            activity_id = next(iter(new_items))
            activity_obj = dl.read(activity_id)
            if activity_obj is not None:
                activity = activity_obj.model_dump(
                    by_alias=True, exclude_none=True
                )

    # TB-04-001: Return 202 with {"activity": {...}}
    return {"activity": activity}
