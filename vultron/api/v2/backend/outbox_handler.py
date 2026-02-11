#!/usr/bin/env python

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
"""
Provides an outbox handler for Vultron Actors.
"""
import logging

from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

logger = logging.getLogger(__name__)


def handle_outbox_item(actor_id: str, obj):
    """
    Handle a single item in the Actor's outbox.

    Args:
        actor_id: The ID of the Actor whose outbox is being processed.
        obj: The Activity item to process.
    Returns:
        None
    Raises:
        ValueError: If the object type is invalid for the outbox.

    """
    logger.info(f"Processing outbox item for actor '{actor_id}'")

    # Here you would implement the logic to handle the outbox item,
    # such as sending it to another actor or processing it further.
    logger.info(f"Outbox item:\n{obj}")


async def outbox_handler(actor_id: str) -> None:
    """
    Process the outbox for the given actor.

    Args:
        actor_id: The ID of the Actor whose outbox is being processed.

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
    while actor.outbox.items:
        item = actor.outbox.items.pop(0)

        try:
            handle_outbox_item(actor_id, item)
        except Exception as e:
            logger.error(
                f"Error processing outbox item for actor {actor_id}: {e}"
            )
            logger.debug(
                f"Item causing error: {item.model_dump_json(indent=2, exclude_none=True)}"
            )
            # put the item back in the inbox for retry
            actor.outbox.items.insert(0, item)
            err_count += 1
            if err_count > 3:
                logger.error(
                    f"Too many errors processing inbox for actor {actor_id}, aborting."
                )
                break
