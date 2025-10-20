#!/usr/bin/env python
"""
Vultron API Routers
"""
#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
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

from fastapi import APIRouter, HTTPException, BackgroundTasks, status, Depends

from vultron.api.v2.backend.actors import ACTOR_REGISTRY
from vultron.api.v2.backend.inbox_handler import (
    inbox_handler,
)
from vultron.api.v2.backend.registry import AsActivityType, ACTIVITY_HANDLERS
from vultron.as_vocab import VOCABULARY
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.base.objects.collections import as_OrderedCollection
from vultron.scripts import vocab_examples

logger = logging.getLogger("uvicorn.error")

# Register example actors in the ACTOR_REGISTRY
for _actor in [
    vocab_examples.finder(),
    vocab_examples.vendor(),
    vocab_examples.coordinator(),
]:
    ACTOR_REGISTRY.register_actor(_actor)

router = APIRouter(prefix="/actors", tags=["Actors"])


@router.get(
    "/",
    response_model=list[as_Actor],
    response_model_exclude_none=True,
    description="Returns a list of Actor examples.",
)
async def get_actors() -> list[as_Actor]:
    """Returns a list of Actor examples."""
    return ACTOR_REGISTRY.list_actors()


@router.get(
    "/{actor_id}",
    response_model=as_Actor,
    response_model_exclude_none=True,
    description="Returns an Actor. (stub implementation).",
)
async def get_actor(actor_id: str) -> as_Actor:
    """Returns an Actor example based on the provided actor_id."""
    actor = ACTOR_REGISTRY.get_actor(actor_id)
    if actor is None:
        raise HTTPException(status_code=404, detail="Actor not found.")
    return actor


@router.get(
    "/{actor_id}/inbox",
    response_model=as_OrderedCollection,
    response_model_exclude_none=True,
    summary="Get Actor Inbox",
    description="Returns the Actor's Inbox. (stub implementation).",
)
async def get_actor_inbox(actor_id: str) -> as_OrderedCollection:
    """Returns the Actor's Inbox."""
    actor: as_Actor = await get_actor(actor_id)

    return actor.inbox


def parse_activity(body: dict) -> AsActivityType:
    """Parses the incoming request body into an as_Activity object.
    Args:
        body: The request body as a dictionary.
    Returns:
        An as_Activity object.
    Raises:
        HTTPException: If the activity type is unknown or validation fails.
    """
    as_type = body.get("type")
    if as_type is None:
        as_type = body.get("asType")

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

    if cls not in ACTIVITY_HANDLERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No handler registered for this activity type.",
        )

    try:
        return cls.model_validate(body)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )


@router.post(
    "/{actor_id}/inbox",
    summary="Add an Activity to the Actor's Inbox.",
    description="Adds an Activity to the Actor's Inbox. (stub implementation).",
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_actor_inbox(
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
    actor: as_Actor = await get_actor(actor_id)
    # append to inbox
    actor.inbox.items.append(activity)

    # Trigger inbox processing (in the background)
    background_tasks.add_task(inbox_handler, actor_id)

    return None


#
# @router.get(
#     "/{actor_id}/outbox",
#     response_model=as_OrderedCollection,
#     response_model_exclude_none=True,
#     summary="Get Actor Outbox",
#     description="Returns the Actor's Outbox. (stub implementation).",
# )
# def get_actor_outbox(actor_id: str) -> as_OrderedCollection:
#     """Returns the Actor's Outbox."""
#     actor: as_Actor = get_actor(actor_id)
#
#     return actor.outbox
#
#
# @router.post(
#     "/{actor_id}/outbox",
#     response_model=as_Create,
#     response_model_exclude_none=True,
#     summary="Add an item to the Actor's Outbox.",
#     description="Adds an item to the Actor's Outbox. (stub implementation).",
# )
# def post_actor_outbox(actor_id: str, item: dict) -> as_Create:
#     """Adds an item to the Actor's Outbox."""
#     # find the item class based on the "type" field
#     obj = obj_from_item(item)
#
#     actor: as_Actor = get_actor(actor_id)
#
#     actor.outbox.items.append(obj)
#
#     return as_Create(
#         object=obj,
#         target=actor_id,
#         actor=actor_id,
#     )
