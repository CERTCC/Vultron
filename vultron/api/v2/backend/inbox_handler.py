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

logger = logging.getLogger("uvicorn.error")


async def inbox_handler(actor_id: str):
    await asyncio.sleep(1)
    actor = ACTOR_REGISTRY.get_actor(actor_id)
    if actor is None:
        logger.warning(f"Actor {actor_id} not found in inbox_handler.")

    logger.info(f"Processing inbox for actor {actor_id}")
    # Simulate processing each item in the inbox
    while actor.inbox.items:
        item = actor.inbox.items.pop(0)
        logger.info(f"Processed item {item} for actor {actor_id}")
        await asyncio.sleep(0.1)  # Simulate some processing time

    return True
