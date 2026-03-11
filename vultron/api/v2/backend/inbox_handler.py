#!/usr/bin/env python
"""
Vultron Actor Inbox Handler
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
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import logging

from vultron.api.v2.backend import handlers  # noqa: F401
from vultron.api.v2.backend.handler_map import SEMANTICS_HANDLERS
from vultron.api.v2.data.actor_io import get_actor_io
from vultron.api.v2.data.rehydration import rehydrate
from vultron.behavior_dispatcher import (
    ActivityDispatcher,
    get_dispatcher,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.types import DispatchActivity
from vultron.wire.as2.extractor import extract_intent
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger(__name__)


def prepare_for_dispatch(activity: as_Activity) -> DispatchActivity:
    """
    Prepares an activity for dispatch by extracting its message semantics and packaging it into a DispatchActivity.
    """
    logger.debug(
        f"Preparing activity '{activity.as_id}' of type '{activity.as_type}' for dispatch."
    )

    event = extract_intent(activity)

    # For CREATE-type activities, the object may be inline (not yet in DataLayer)
    obj = getattr(activity, "as_object", None)
    wire_object = (
        obj if (obj is not None and not isinstance(obj, str)) else None
    )

    dispatch_msg = DispatchActivity(
        semantic_type=event.semantic_type,
        activity_id=activity.as_id,
        payload=event,
        wire_activity=activity,
        wire_object=wire_object,
    )
    logger.debug(
        f"Prepared dispatch message with semantics '{dispatch_msg.semantic_type}' for activity '{dispatch_msg.payload.activity_id}'"
    )
    return dispatch_msg


_DISPATCHER: ActivityDispatcher | None = None


def init_dispatcher(dl: DataLayer) -> None:
    """Initialise the module-level dispatcher with an injected DataLayer.

    Must be called once during application startup (e.g. from the FastAPI
    lifespan event) before any inbox items are processed.  Calling it more
    than once (e.g. in tests) is allowed — the dispatcher is simply replaced.

    Args:
        dl: The DataLayer instance to inject into the dispatcher.
    """
    global _DISPATCHER
    _DISPATCHER = get_dispatcher(handler_map=SEMANTICS_HANDLERS, dl=dl)
    logger.info("Initialised inbox dispatcher: %s", type(_DISPATCHER).__name__)


def dispatch(dispatchable: DispatchActivity) -> None:
    """
    Dispatches the given activity using the module-level dispatcher.

    Args:
        dispatchable: The DispatchActivity to dispatch.
    Raises:
        RuntimeError: If the dispatcher has not been initialised via
            :func:`init_dispatcher`.
    """
    if _DISPATCHER is None:
        raise RuntimeError(
            "Inbox dispatcher not initialised. "
            "Call init_dispatcher() during application startup."
        )
    logger.debug(
        f"Dispatching activity '{dispatchable.activity_id}' with semantics '{dispatchable.semantic_type}'"
    )
    _DISPATCHER.dispatch(dispatchable)


def handle_inbox_item(actor_id: str, obj: as_Activity) -> None:
    """
    Handle a single item in the Actor's inbox.

    Args:
        actor_id: The ID of the Actor whose inbox is being processed.
        obj: The Activity item to process. This should be an instance of as_Activity,
             and will be rehydrated to its specific subclass.

    Returns:
        None
    Raises:
        ValueError: If the object type is invalid for the inbox.

    """
    logger.info(f"Processing item '{obj.name}' for actor '{actor_id}'")

    logger.debug(
        f"Validated object:\n{obj.model_dump_json(indent=2,exclude_none=True)}"
    )

    dispatchable = prepare_for_dispatch(activity=obj)
    dispatch(dispatchable=dispatchable)


async def inbox_handler(actor_id: str, dl: DataLayer) -> None:
    """
    Process the inbox for the given actor.

    Args:
        actor_id: The ID of the Actor whose inbox is being processed.
        dl: The DataLayer instance to use for persistence operations.
    Returns:
        None
    """
    actor = dl.read(actor_id)
    if actor is None:
        logger.warning(f"Actor {actor_id} not found in inbox_handler.")

    logger.info(f"Processing inbox for actor {actor_id}")

    err_count = 0

    actor_io = get_actor_io(actor_id, raise_on_missing=True)

    while actor_io.inbox.items:
        item = actor_io.inbox.items.pop(0)

        item = rehydrate(item)

        logger.debug(f"Rehydrated item from inbox: {item.as_type}")
        if hasattr(item, "as_object"):
            logger.debug(
                f"Item has transitive object of type: {item.as_object.as_type}"
            )

        try:
            handle_inbox_item(actor_id=actor_id, obj=item)
        except Exception as e:
            logger.error(
                f"Error processing inbox item for actor {actor_id}: {e}"
            )
            logger.debug(
                f"Item causing error: {item.model_dump_json(indent=2, exclude_none=True)}"
            )
            # put the item back in the inbox for retry
            actor_io.inbox.items.insert(0, item)
            err_count += 1
            if err_count > 3:
                logger.error(
                    f"Too many errors processing inbox for actor {actor_id}, aborting."
                )
                break
