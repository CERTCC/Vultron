#!/usr/bin/env python
"""
Vultron API Routers
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import json
import logging
from typing import Any, Literal, cast

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, Field

from vultron.adapters.utils import make_id
from vultron.adapters.driving.fastapi.inbox_handler import (
    inbox_handler,
)
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import DataLayer, StorableRecord
from vultron.core.use_cases.query.action_rules import (
    ActionRulesRequest,
    GetActionRulesUseCase,
)
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driven.datalayer import get_shared_dl
from vultron.errors import VultronNotFoundError, VultronValidationError
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Actor,
    as_Application,
    as_Group,
)
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.objects.collections import (
    as_OrderedCollection,
)
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary
from vultron.wire.as2.errors import (
    VultronParseError,
    VultronParseMissingTypeError,
)
from vultron.wire.as2.parser import parse_activity as _parse_activity
from vultron.wire.as2.vocab.objects.vultron_actor import (
    VultronOrganization,
    VultronPerson,
    VultronService,
)

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/actors", tags=["Actors"])


@router.get(
    "/",
    response_model=list[as_Actor],
    response_model_exclude_none=True,
    description="Returns a list of Actor examples.",
    operation_id="actors_list",
)
def get_actors(
    datalayer: DataLayer = Depends(get_shared_dl),
) -> list[as_Actor]:
    """Returns a list of Actor examples."""
    types = [
        "Actor",
        "Application",
        "Group",
        "Organization",
        "Person",
        "Service",
    ]
    results = []
    for t in types:
        results.extend(datalayer.get_all(t))

    logger.debug(f"get_actors: found {len(results)} actor records")

    objects: list[as_Actor] = []
    for rec in results:
        try:
            cls = find_in_vocabulary(rec["type_"])
        except KeyError:
            continue
        obj = cls.model_validate(rec["data_"])
        if isinstance(obj, as_Actor):
            objects.append(obj)

    return objects


# ---------------------------------------------------------------------------
# Actor type map — used by create_actor
# ---------------------------------------------------------------------------

_ACTOR_TYPE_MAP: dict[str, type[as_Actor]] = {
    "Person": VultronPerson,
    "Organization": VultronOrganization,
    "Service": VultronService,
    "Application": as_Application,
    "Group": as_Group,
}


class ActorCreateRequest(BaseModel):
    """Request body for ``POST /actors/`` (D5-1-G2).

    Creates a new actor record in the shared DataLayer.  The operation is
    idempotent: if ``id`` is supplied and an actor with that URI already
    exists, the existing record is returned with HTTP 200.
    """

    name: str = Field(description="Display name of the actor.")
    actor_type: Literal[
        "Person", "Organization", "Service", "Application", "Group"
    ] = Field(
        default="Organization",
        description="ActivityStreams actor type.",
    )
    id_: str | None = Field(
        default=None,
        alias="id",
        description=(
            "Full URI for the actor.  Omit to let the server derive one "
            "from ``VULTRON_BASE_URL``."
        ),
    )

    model_config = {"populate_by_name": True}


@router.post(
    "/",
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Create Actor",
    description=(
        "Creates a new actor record in the shared DataLayer. "
        "Idempotent: if an actor with the same ``id`` already exists the "
        "existing record is returned with HTTP 200."
    ),
    operation_id="actors_create",
)
def create_actor(
    request: ActorCreateRequest,
    response: Response,
    datalayer: DataLayer = Depends(get_shared_dl),
) -> as_Actor:
    """Create (or return existing) actor record."""
    actor_id = request.id_ or make_id("actors")

    # Idempotency: return existing record unchanged.
    existing = datalayer.read(actor_id)
    if existing is None:
        existing = datalayer.find_actor_by_short_id(actor_id)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return as_Actor.model_validate(existing)

    actor_cls = _ACTOR_TYPE_MAP.get(request.actor_type, VultronOrganization)
    actor = actor_cls(id_=actor_id, name=request.name)
    datalayer.create(object_to_record(cast(PersistableModel, actor)))
    logger.info("Created actor %s (type=%s)", actor_id, request.actor_type)
    return actor


@router.get(
    "/{actor_id}",
    response_model=as_Actor,
    response_model_exclude_none=True,
    description="Returns an Actor. (stub implementation).",
    operation_id="actors_get",
)
def get_actor(
    actor_id: str, datalayer: DataLayer = Depends(get_shared_dl)
) -> as_Actor:
    """Returns an Actor example based on the provided actor_id."""
    actor = datalayer.read(actor_id)

    # If not found by full ID, try to resolve as short ID
    if not actor:
        actor = datalayer.find_actor_by_short_id(actor_id)

    if not actor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actor not found."
        )

    return as_Actor.model_validate(actor)


@router.get(
    "/{actor_id}/profile",
    response_model_exclude_none=True,
    summary="Get Actor Profile",
    description=(
        "Returns an ActivityStreams actor profile including inbox and outbox "
        "URLs for actor discovery and federation."
    ),
    operation_id="actors_get_profile",
)
def get_actor_profile(
    actor_id: str, datalayer: DataLayer = Depends(get_shared_dl)
):
    """Returns an actor's discovery profile.

    Includes actor metadata (name, type), inbox URL, outbox URL, and any
    other ActivityStreams profile fields present on the actor.  Intended
    for use by remote systems discovering how to interact with this actor.
    The `inbox` and `outbox` fields are returned as URL strings, not
    embedded collection objects.
    """
    actor = datalayer.read(actor_id)

    if not actor:
        actor = datalayer.find_actor_by_short_id(actor_id)

    if not actor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actor not found."
        )

    as_actor = as_Actor.model_validate(actor)
    profile = as_actor.model_dump(by_alias=True, exclude_none=True)
    profile["inbox"] = as_actor.inbox.id_
    profile["outbox"] = as_actor.outbox.id_
    return profile


@router.get(
    "/{actor_id}/cases/{case_id}/action-rules",
    summary="Get CVD Action Rules for an Actor in a Case",
    description=(
        "Returns the set of valid CVD actions available to an actor in a "
        "specific case. The actor/case pair is resolved to the matching "
        "CaseParticipant internally."
    ),
    operation_id="actors_get_action_rules",
)
def get_action_rules(
    actor_id: str,
    case_id: str,
    dl: DataLayer = Depends(get_shared_dl),
) -> dict:
    """Return valid CVD actions for an actor in a specific case."""
    try:
        req = ActionRulesRequest(case_id=case_id, actor_id=actor_id)
        return GetActionRulesUseCase(dl=dl, request=req).execute()
    except VultronNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except VultronValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )


@router.get(
    "/{actor_id}/inbox",
    response_model=as_OrderedCollection,
    response_model_exclude_none=True,
    summary="Get Actor Inbox",
    description="Returns the Actor's Inbox. (stub implementation).",
    operation_id="actors_get_inbox",
)
def get_actor_inbox(
    actor_id: str, datalayer: DataLayer = Depends(get_shared_dl)
) -> as_OrderedCollection:
    """Returns the Actor's Inbox."""

    actor_record = datalayer.read(actor_id)

    if not actor_record:
        actor_record = datalayer.find_actor_by_short_id(actor_id)

    if not actor_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Actor not found.",
        )

    actor = as_Actor.model_validate(actor_record)
    actor_dl = datalayer.clone_for_actor(actor.id_)
    items = cast(
        list[as_Object | as_Link | str | None], list(actor_dl.inbox_list())
    )
    return as_OrderedCollection(items=items)


def parse_activity(body: dict[str, Any]) -> as_Activity:
    """HTTP adapter: parse request body and map wire errors to HTTP responses.

    Delegates AS2 parsing to the wire layer and converts domain parse errors
    into appropriate HTTP status codes for FastAPI.

    Args:
        body: The request body as a dictionary.

    Returns:
        A typed as_Activity subclass instance.

    Raises:
        HTTPException: 400 if the `type` field is missing; 422 for all other
            parse failures (unknown type, validation error).
    """
    logger.info(
        "Parsing activity from request body (type=%r):\n%s",
        body.get("type"),
        json.dumps(body, indent=2, default=str),
    )
    try:
        return _parse_activity(body)
    except VultronParseMissingTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except VultronParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )


def _resolve_actor_or_404(actor_id: str, dl: DataLayer) -> as_Actor:
    actor_record = dl.read(actor_id)
    if actor_record is None:
        actor_record = dl.find_actor_by_short_id(actor_id)
    if actor_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actor not found."
        )
    return as_Actor.model_validate(actor_record)


def _activity_already_received(actor: as_Actor, activity_id: str) -> bool:
    return bool(
        actor.inbox
        and hasattr(actor.inbox, "items")
        and activity_id in actor.inbox.items
    )


def _store_nested_inbox_object(dl: DataLayer, activity: as_Activity) -> None:
    nested = getattr(activity, "object_", None)
    if nested is None or isinstance(nested, str):
        return
    if not (
        hasattr(nested, "id_")
        and hasattr(nested, "type_")
        and nested.type_ is not None
        and not nested.type_.startswith("as_")
    ):
        return

    try:
        dl.create(object_to_record(cast(PersistableModel, nested)))
    except ValueError:
        pass


def _store_inbox_activity(dl: DataLayer, activity: as_Activity) -> None:
    try:
        dl.create(object_to_record(activity))
    except ValueError:
        logger.debug(
            "Activity %s already exists in shared DL; skipping re-store.",
            activity.id_,
        )


def _record_inbox_receipt(
    dl: DataLayer,
    actor: as_Actor,
    activity_id: str,
    canonical_actor_id: str,
) -> None:
    if not actor.inbox or not hasattr(actor.inbox, "items"):
        return

    actor.inbox.items.append(activity_id)
    dl.update(
        actor.id_,
        StorableRecord(
            id_=actor.id_,
            type_=actor.type_ or "Actor",
            data_=actor.model_dump(mode="json"),
        ),
    )
    logger.debug(
        f"Added activity {activity_id} to actor {canonical_actor_id} inbox record"
    )


@router.post(
    "/{actor_id}/inbox/",
    summary="Add an Activity to the Actor's Inbox.",
    description="Adds an Activity to the Actor's Inbox. (stub implementation).",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="actors_post_inbox",
)
def post_actor_inbox(
    actor_id: str,
    # as_Activity is a problem, because its subclasses have different required fields,
    # so we really want to accept any subclass that we have a registered handler for here.
    request: Request,
    background_tasks: BackgroundTasks,
    activity: as_Activity = Depends(parse_activity),
    dl: DataLayer = Depends(get_shared_dl),
) -> None:
    """Adds an item to the Actor's Inbox.
    The 202 Accepted status code indicates that the request has been accepted for
    processing, but the processing has not been completed. This is appropriate here
    because the inbox processing is handled asynchronously in the background.
    Args:
        actor_id: The ID of the Actor whose Inbox to add the item to.
        request: The FastAPI Request (used to resolve the per-app emitter).
        activity: The Activity item to add to the Inbox.
        background_tasks: FastAPI BackgroundTasks instance to schedule background tasks.
    Returns:
        None
    Raises:
        HTTPException: If the Actor is not found.
    """
    actor = _resolve_actor_or_404(actor_id, dl)
    canonical_actor_id = actor.id_

    if _activity_already_received(actor, activity.id_):
        logger.info(
            "Activity %s already received by %s; ignoring duplicate submission.",
            activity.id_,
            canonical_actor_id,
        )
        return None

    _store_nested_inbox_object(dl, activity)
    _store_inbox_activity(dl, activity)

    logger.debug(
        f"Posting activity to actor {canonical_actor_id} inbox: {activity}"
    )
    _record_inbox_receipt(dl, actor, activity.id_, canonical_actor_id)

    actor_dl = dl.clone_for_actor(canonical_actor_id)
    actor_dl.inbox_append(activity.id_)
    emitter = getattr(request.app.state, "emitter", None)
    background_tasks.add_task(
        inbox_handler, canonical_actor_id, dl, actor_dl, emitter
    )
    return None


@router.post(
    "/{actor_id}/outbox/",
    summary="Add an Activity to the Actor's Outbox.",
    description="Adds an Activity to the Actor's Outbox. (stub implementation).",
    status_code=status.HTTP_200_OK,
    operation_id="actors_post_outbox",
)
def post_actor_outbox(
    actor_id: str,
    activity: as_Activity,
    request: Request,
    background_tasks: BackgroundTasks,
    dl: DataLayer = Depends(get_shared_dl),
) -> None:
    """Adds an item to the Actor's Outbox.
    Args:
        actor_id: The ID of the Actor whose Outbox to add the item to.
        activity: The Activity item to add to the Outbox.
        request: The FastAPI Request (used to resolve the per-app emitter).
        background_tasks: FastAPI BackgroundTasks instance to schedule background tasks.
    Returns:
        None
    Raises:
        HTTPException: If the Actor is not found.
    """
    actor_record = dl.read(actor_id) or dl.find_actor_by_short_id(actor_id)
    actor = as_Actor.model_validate(actor_record) if actor_record else None

    if not actor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actor not found."
        )

    # Normalise to the canonical actor URI so that short-ID and full-ID
    # callers always scope to the same DataLayer namespace.
    canonical_actor_id = actor.id_

    # actor.id_ must match activity.actor or activity.actor.id_
    if isinstance(activity.actor, str):
        activity_actor_id = activity.actor
    elif activity.actor is not None and hasattr(activity.actor, "id_"):
        activity_actor_id = activity.actor.id_
    else:
        activity_actor_id = None

    if activity_actor_id != canonical_actor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activity actor does not match actor_id.",
        )

    logger.debug(
        f"Posting activity to actor {canonical_actor_id} outbox: {activity}"
    )

    # Use the actor-scoped DataLayer for operational data
    actor_dl = dl.clone_for_actor(canonical_actor_id)
    actor_dl.create(object_to_record(activity))
    actor_dl.outbox_append(activity.id_)

    emitter = getattr(request.app.state, "emitter", None)
    background_tasks.add_task(
        outbox_handler, canonical_actor_id, actor_dl, dl, emitter
    )

    return None
