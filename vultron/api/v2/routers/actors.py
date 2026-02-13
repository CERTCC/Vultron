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

from vultron.api.v2.backend.inbox_handler import (
    inbox_handler,
)
from vultron.api.v2.backend.outbox_handler import outbox_handler
from vultron.api.v2.data.actor_io import get_actor_io
from vultron.api.v2.datalayer.db_record import object_to_record
from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
from vultron.as_vocab import VOCABULARY
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.base.objects.collections import as_OrderedCollection
from vultron.as_vocab.base.registry import find_in_vocabulary
from vultron.as_vocab.type_helpers import AsActivityType

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/actors", tags=["Actors"])


@router.get(
    "/",
    response_model=list[as_Actor],
    response_model_exclude_none=True,
    description="Returns a list of Actor examples.",
)
def get_actors() -> list[as_Actor]:
    """Returns a list of Actor examples."""

    datalayer = get_datalayer()
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

    logger.info(f"results: {results}")

    objects = []
    for rec in results:
        logger.info(f"rec: {rec}")
        cls = find_in_vocabulary(rec["type_"])
        obj = cls.model_validate(rec["data_"])
        objects.append(obj)

    return objects


@router.get(
    "/{actor_id}",
    response_model=as_Actor,
    response_model_exclude_none=True,
    description="Returns an Actor. (stub implementation).",
)
def get_actor(actor_id: str) -> as_Actor:
    """Returns an Actor example based on the provided actor_id."""
    datalayer = get_datalayer()
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
    "/{actor_id}/inbox",
    response_model=as_OrderedCollection,
    response_model_exclude_none=True,
    summary="Get Actor Inbox",
    description="Returns the Actor's Inbox. (stub implementation).",
)
def get_actor_inbox(actor_id: str) -> as_OrderedCollection:
    """Returns the Actor's Inbox."""

    # Try to resolve actor ID (handles both full URIs and short IDs)
    datalayer = get_datalayer()
    actor = datalayer.read(actor_id)

    if not actor:
        actor = datalayer.find_actor_by_short_id(actor_id)

    if not actor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Actor not found.",
        )

    # Use the full actor ID for actor_io lookup
    full_actor_id = actor.as_id if hasattr(actor, "as_id") else actor_id

    actor_io = get_actor_io(full_actor_id, init=False, raise_on_missing=False)
    if actor_io is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Actor Inbox not found.",
        )

    return as_OrderedCollection(items=actor_io.inbox.items)


def parse_activity(body: dict) -> AsActivityType:
    """Parses the incoming request body into an as_Activity object.
    Args:
        body: The request body as a dictionary.
    Returns:
        An as_Activity object.
    Raises:
        HTTPException: If the activity type is unknown or validation fails.
    """
    logger.info(f"Parsing activity from request body. {body}")

    as_type = body.get("type")
    if as_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'type' field in activity.",
        )

    cls = VOCABULARY.activities.get(as_type)
    if cls is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Unrecognized activity type.",
        )

    try:
        return cls.model_validate(body)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )


@router.post(
    "/{actor_id}/inbox/",
    summary="Add an Activity to the Actor's Inbox.",
    description="Adds an Activity to the Actor's Inbox. (stub implementation).",
    status_code=status.HTTP_202_ACCEPTED,
)
def post_actor_inbox(
    actor_id: str,
    # as_Activity is a problem, because its subclasses have different required fields,
    # so we really want to accept any subclass that we have a registered handler for here.
    background_tasks: BackgroundTasks,
    activity: as_Activity = Depends(parse_activity),
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
    dl = get_datalayer()
    # Try to read actor by full ID first
    actor = dl.read(actor_id)

    # If not found, try to resolve as short ID (e.g., "vendorco" -> "https://.../vendorco")
    if actor is None:
        actor = dl.find_actor_by_short_id(actor_id)

    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actor not found."
        )

    # Extract the full actor ID for subsequent operations
    full_actor_id = actor.as_id if hasattr(actor, "as_id") else actor_id

    dl.create(object_to_record(activity))

    logger.debug(
        f"Posting activity to actor {full_actor_id} inbox: {activity}"
    )
    actor_io = get_actor_io(full_actor_id, init=True, raise_on_missing=False)
    # append activity ID to inbox
    actor_io.inbox.items.append(activity.as_id)

    # Update the database actor's inbox collection to persist the activity
    actor = as_Actor.model_validate(actor)

    if actor.inbox:
        actor.inbox.items.append(activity.as_id)
        dl.update(actor.as_id, object_to_record(actor))
        logger.info(
            f"Added activity {activity.as_id} to actor {actor.as_id} inbox"
        )
    else:
        logger.error(f"Actor {actor.as_id} has no inbox - cannot add activity")

    # Trigger inbox processing (in the background) using the full_actor_id
    background_tasks.add_task(inbox_handler, full_actor_id)

    return None


@router.post(
    "/{actor_id}/outbox/",
    summary="Add an Activity to the Actor's Outbox.",
    description="Adds an Activity to the Actor's Outbox. (stub implementation).",
    status_code=status.HTTP_200_OK,
)
def post_actor_outbox(
    actor_id: str, activity: as_Activity, background_tasks: BackgroundTasks
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
    dl = get_datalayer()
    actor = dl.read(actor_id)
    actor = as_Actor.model_validate(actor)

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

    actor_io = get_actor_io(actor_id, init=False, raise_on_missing=True)

    dl.create(object_to_record(activity))

    # append activity ID to outbox
    actor_io.outbox.items.append(activity.as_id)

    # Update the database actor's outbox collection to persist the activity
    if actor.outbox:
        actor.outbox.items.append(activity.as_id)
        dl.update(actor.as_id, object_to_record(actor))

    # Trigger outbox processing (in the background)
    background_tasks.add_task(outbox_handler, actor_id)

    return None
