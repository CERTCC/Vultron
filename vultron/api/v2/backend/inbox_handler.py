#!/usr/bin/env python
"""
Vultron Actor Inbox Handler
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

import asyncio
import logging

from vultron.api.v2.backend.actors import ACTOR_REGISTRY
from vultron.as_vocab.base.base import as_Base

logger = logging.getLogger("uvicorn.error")


def handle_inbox_item(actor_id: str, obj: as_Base):
    logger.info(f"Processing item {obj.name} for actor {actor_id}")

    logger.info(
        f"Validated object:\n{obj.model_dump_json(indent=2,exclude_none=True)}"
    )
    match obj.as_type:
        # we should only be receiving Activities in the inbox.

        # bare objects are an error.

        case "Note":
            logger.info(f"Actor {actor_id} received Note: {obj.name}")
        case "Create":
            logger.info(
                f"Actor {actor_id} received Create activity: {obj.name}"
            )
        case "Offer":
            logger.info(
                f"Actor {actor_id} received Offer activity: {obj.name}"
            )
        case "Accept":
            logger.info(
                f"Actor {actor_id} received Accept activity: {obj.name}"
            )
        case "Reject":
            logger.info(
                f"Actor {actor_id} received Reject activity: {obj.name}"
            )
        case "Announce":
            logger.info(
                f"Actor {actor_id} received Announce activity: {obj.name}"
            )
        case "Follow":
            logger.info(
                f"Actor {actor_id} received Follow activity: {obj.name}"
            )
        case "Invite":
            logger.info(
                f"Actor {actor_id} received Invite activity: {obj.name}"
            )
        case _:
            logger.warning(
                f"Actor {actor_id} received unknown object type {obj.as_type}: {obj.name}"
            )


async def inbox_handler(actor_id: str):
    await asyncio.sleep(1)
    actor = ACTOR_REGISTRY.get_actor(actor_id)
    if actor is None:
        logger.warning(f"Actor {actor_id} not found in inbox_handler.")

    logger.info(f"Processing inbox for actor {actor_id}")
    # Simulate processing each item in the inbox
    err_count = 0
    while actor.inbox.items:
        item = actor.inbox.items.pop(0)
        try:
            handle_inbox_item(actor_id, item)
        except Exception as e:
            logger.error(
                f"Error processing item {item} for actor {actor_id}: {e}"
            )
            # put the item back in the inbox for retry
            actor.inbox.items.insert(0, item)
            err_count += 1
            if err_count > 3:
                logger.error(
                    f"Too many errors processing inbox for actor {actor_id}, aborting."
                )
                break

        await asyncio.sleep(0.1)  # Simulate some processing time

    return True
