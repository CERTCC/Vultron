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
from vultron.api.v2.backend.handlers.registry import (
    get_activity_handler,
)
from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
from vultron.api.v2.data.actor_io import get_actor_io
from vultron.api.v2.data.rehydration import rehydrate
from vultron.as_vocab import VOCABULARY
from vultron.as_vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger(__name__)


def handle_inbox_item(actor_id: str, obj: as_Activity):
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

    logger.info(
        f"Validated object:\n{obj.model_dump_json(indent=2,exclude_none=True)}"
    )

    # we should only be receiving Activities in the inbox.
    if obj.as_type not in VOCABULARY.activities:
        raise ValueError(
            f"Invalid object type {obj.as_type} in inbox for actor {actor_id}"
        )

    rehydrated = rehydrate(obj=obj)

    logger.debug(
        f"Looking up handler for activity type '{rehydrated.as_type}'"
    )
    handler = get_activity_handler(rehydrated)
    logger.debug(f"Handler found: {handler}")

    if handler is None:
        raise ValueError(
            f"No handler registered for activity type '{rehydrated.as_type}'"
        )

    logger.debug(
        f"Found handler '{handler}' for activity type '{rehydrated.as_type}'"
    )
    handler(actor_id, rehydrated)


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
    # Simulate processing each item in the inbox
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

        # in principle because of the POST {actor_id}/inbox method validation,
        # the only items in the inbox should be Activities with registered handlers,
        # but we'll let handle_inbox_item deal with verifying that
        try:
            handle_inbox_item(actor_id, item)
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
