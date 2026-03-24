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

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from vultron.adapters.driving.fastapi.inbox_handler import (
    inbox_handler,
)
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.core.ports.datalayer import DataLayer
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driven.datalayer_tinydb import get_datalayer
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.collections import (
    as_OrderedCollection,
)
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary
from vultron.wire.as2.vocab.type_helpers import AsActivityType
from vultron.wire.as2.errors import (
    VultronParseError,
    VultronParseMissingTypeError,
)
from vultron.wire.as2.parser import parse_activity as _parse_activity

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/actors", tags=["Actors"])


def _shared_dl() -> DataLayer:
    """Dependency: always returns the shared (non-actor-scoped) DataLayer.

    Using this wrapper prevents FastAPI from forwarding the ``actor_id`` path
    parameter into ``get_datalayer(actor_id=…)``, which would return a scoped
    DataLayer that contains no actors.
    """
    return get_datalayer()


@router.get(
    "/",
    response_model=list[as_Actor],
    response_model_exclude_none=True,
    description="Returns a list of Actor examples.",
    operation_id="actors_list",
)
def get_actors(
    datalayer: DataLayer = Depends(_shared_dl),
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

    objects = []
    for rec in results:
        cls = find_in_vocabulary(rec["type_"])
        obj = cls.model_validate(rec["data_"])
        objects.append(obj)

    return objects


@router.get(
    "/{actor_id}",
    response_model=as_Actor,
    response_model_exclude_none=True,
    description="Returns an Actor. (stub implementation).",
    operation_id="actors_get",
)
def get_actor(
    actor_id: str, datalayer: DataLayer = Depends(_shared_dl)
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
    actor_id: str, datalayer: DataLayer = Depends(_shared_dl)
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
    profile["inbox"] = as_actor.inbox.as_id
    profile["outbox"] = as_actor.outbox.as_id
    return profile


@router.get(
    "/{actor_id}/inbox",
    response_model=as_OrderedCollection,
    response_model_exclude_none=True,
    summary="Get Actor Inbox",
    description="Returns the Actor's Inbox. (stub implementation).",
    operation_id="actors_get_inbox",
)
def get_actor_inbox(
    actor_id: str, datalayer: DataLayer = Depends(_shared_dl)
) -> as_OrderedCollection:
    """Returns the Actor's Inbox."""

    actor = datalayer.read(actor_id)

    if not actor:
        actor = datalayer.find_actor_by_short_id(actor_id)

    if not actor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Actor not found.",
        )

    actor_dl = get_datalayer(actor_id)
    items = actor_dl.inbox_list()
    return as_OrderedCollection(items=items)


def parse_activity(body: dict) -> AsActivityType:
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
    logger.info(f"Parsing activity from request body. {body}")
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
    background_tasks: BackgroundTasks,
    activity: as_Activity = Depends(parse_activity),
    dl: DataLayer = Depends(_shared_dl),
) -> None:
    """Adds an item to the Actor's Inbox.
    The 202 Accepted status code indicates that the request has been accepted for
    processing, but the processing has not been completed. This is appropriate here
    because the inbox processing is handled asynchronously in the background.
    Args:
        actor_id: The ID of the Actor whose Inbox to add the item to.
        activity: The Activity item to add to the Inbox.
        background_tasks: FastAPI BackgroundTasks instance to schedule background tasks.
    Returns:
        None
    Raises:
        HTTPException: If the Actor is not found.
    """
    # Try to read actor by full ID first (shared DataLayer for identity lookup)
    actor = dl.read(actor_id)

    # If not found, try to resolve as short ID (e.g., "vendorco" -> "https://.../vendorco")
    if actor is None:
        actor = dl.find_actor_by_short_id(actor_id)

    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actor not found."
        )

    # Store activity in the SHARED DataLayer so cross-actor lookups work.
    # (Operational data must be accessible to all actors' use cases and
    # rehydration; actor-scoped DL is used only for queue management.)
    dl.create(object_to_record(activity))

    logger.debug(f"Posting activity to actor {actor_id} inbox: {activity}")

    # Append activity ID to the actor's inbox.items in the shared DL for
    # visibility/history (mirrors the pre-ACT-2 behavior). This record is
    # NOT removed by the inbox handler; it acts as a persistent received-log.
    if actor.inbox and hasattr(actor.inbox, "items"):
        actor.inbox.items.append(activity.as_id)
        dl.save(actor)
        logger.debug(
            f"Added activity {activity.as_id} to actor {actor.as_id} inbox record"
        )

    # Queue the activity ID in the actor-scoped DataLayer inbox.
    actor_dl = get_datalayer(actor_id)
    actor_dl.inbox_append(activity.as_id)

    # Trigger inbox processing: pass short actor_id, shared DL for data,
    # and actor-scoped DL for queue management.
    background_tasks.add_task(inbox_handler, actor_id, dl, actor_dl)

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
    background_tasks: BackgroundTasks,
    dl: DataLayer = Depends(_shared_dl),
) -> None:
    """Adds an item to the Actor's Outbox.
    Args:
        actor_id: The ID of the Actor whose Outbox to add the item to.
        activity: The Activity item to add to the Outbox.
        background_tasks: FastAPI BackgroundTasks instance to schedule background tasks.
    Returns:
        None
    Raises:
        HTTPException: If the Actor is not found.
    """
    actor = dl.read(actor_id) or dl.find_actor_by_short_id(actor_id)
    actor = as_Actor.model_validate(actor) if actor else None

    if not actor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actor not found."
        )

    # actor.as_id must match activity.actor or activity.actor.as_id
    if isinstance(activity.actor, str):
        activity_actor_id = activity.actor
    elif hasattr(activity.actor, "as_id"):
        activity_actor_id = activity.actor.as_id
    else:
        activity_actor_id = None

    if activity_actor_id != actor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activity actor does not match actor_id.",
        )

    logger.debug(f"Posting activity to actor {actor_id} outbox: {activity}")

    # Use the actor-scoped DataLayer for operational data
    actor_dl = get_datalayer(actor_id)
    actor_dl.create(object_to_record(activity))
    actor_dl.outbox_append(activity.as_id)

    # Trigger outbox processing (in the background)
    background_tasks.add_task(outbox_handler, actor_id, actor_dl)

    return None
