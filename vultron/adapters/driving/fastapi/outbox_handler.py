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

from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


def handle_outbox_item(actor_id: str, activity_id: str) -> None:
    """Handle a single item in the Actor's outbox.

    Args:
        actor_id: The ID of the Actor whose outbox is being processed.
        activity_id: The ID of the activity to process.
    """
    logger.info("Processing outbox item for actor '%s'", actor_id)
    # Delivery implementation deferred to OX-1.1 (per ADR-0012 OX-B decision).
    logger.info("Outbox item: %s", activity_id)


async def outbox_handler(actor_id: str, dl: DataLayer) -> None:
    """Process the outbox for the given actor.

    Reads pending activity IDs from the DataLayer outbox queue and
    dispatches each one.  Delivery to remote actors is deferred until
    OX-1.1 (per ADR-0012 OX-B decision).

    Args:
        actor_id: The ID of the Actor whose outbox is being processed.
        dl: The DataLayer instance scoped to the current actor.
    """
    actor = dl.read(actor_id)
    if actor is None:
        logger.warning("Actor %s not found in outbox_handler.", actor_id)
        return

    logger.info("Processing outbox for actor %s", actor_id)
    err_count = 0
    while dl.outbox_list():
        activity_id = dl.outbox_pop()
        if activity_id is None:
            break

        try:
            handle_outbox_item(actor_id, activity_id)
        except Exception as e:
            logger.error(
                "Error processing outbox item for actor %s: %s", actor_id, e
            )
            dl.outbox_append(activity_id)
            err_count += 1
            if err_count > 3:
                logger.error(
                    "Too many errors processing outbox for actor %s, aborting.",
                    actor_id,
                )
                break
