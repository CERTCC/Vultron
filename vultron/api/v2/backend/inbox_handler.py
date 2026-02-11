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
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import logging

from vultron.api.v2.backend import handlers  # noqa: F401
from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
from vultron.api.v2.data.actor_io import get_actor_io
from vultron.api.v2.data.rehydration import rehydrate
from vultron.api.v2.errors import VultronApiValidationError
from vultron.as_vocab import VOCABULARY
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.behavior_dispatcher import DispatchActivity, prepare_for_dispatch
from vultron.behavior_dispatcher import get_dispatcher


logger = logging.getLogger(__name__)

DISPATCHER = get_dispatcher()
logger.info("Using dispatcher: %s", type(DISPATCHER).__name__)


def raise_if_not_valid_activity(obj: as_Activity) -> None:
    """
    Raises a VultronApiValidationError if the given object is not a valid Activity.

    Args:
        obj: The object to validate.
    Returns:
        None
    Raises:
        VultronApiValidationError: If the object is not a valid Activity.
    """
    if obj.as_type not in VOCABULARY.activities:
        raise VultronApiValidationError(
            f"Invalid object type {obj.as_type} in inbox item, expected an Activity."
        )


def dispatch(dispatchable: DispatchActivity) -> None:
    """
    Dispatches the given activity using the global dispatcher.
    Args:
        dispatchable: The DispatchActivity to dispatch.
    Returns:
        None
    """
    logger.debug(
        f"Dispatching activity '{dispatchable.activity_id}' with semantics '{dispatchable.semantic_type}'"
    )
    DISPATCHER.dispatch(dispatchable)


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

    raise_if_not_valid_activity(obj)

    dispatchable = prepare_for_dispatch(activity=obj)
    dispatch(dispatchable=dispatchable)


async def inbox_handler(actor_id: str) -> None:
    """
    Process the inbox for the given actor.
    Args:
        actor_id: The ID of the Actor whose inbox is being processed.
    Returns:
        None
    Raises:
        None
    """
    dl = get_datalayer()
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
