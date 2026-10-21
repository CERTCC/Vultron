#!/usr/bin/env python
"""Replay every hosted actor's inbox queue when the process starts (IE-06-006).

An item left queued by a previous run, for example by a process stop during
its replay attempt (IE-06-005), is otherwise replayed only when the next
delivery reaches the same actor, which may never happen.  The app lifespan
calls :func:`replay_hosted_inbox_queues` once at startup.  It re-runs what is
queued, with the bounded retry and dead letter of a replay after a delivery
(IE-06-004); it repairs nothing.
"""

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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
from typing import Any

from vultron.adapters.driven import actor_hosts
from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    replay_inbox_queue,
)

logger = logging.getLogger(__name__)


async def replay_hosted_inbox_queues(emitter: Any = None) -> int:
    """Replay the inbox queue of every actor this node hosts.

    Actors are found from the stores that exist, as the startup recovery
    of pending case creation finds them (ADR-0073: there is no store that
    sees every actor's rows).  Each actor's queue is replayed under that
    actor's inbox lock and off the event loop
    (:func:`~vultron.adapters.driving.fastapi.inbox_orchestration.replay_inbox_queue`).
    An actor whose replay raises is logged, and the next actor is still
    replayed; its items stay queued for the next replay (IE-06-005).

    Args:
        emitter: The app's ActivityEmitter, for the outbox drain after each
            actor's replay.

    Returns:
        The number of actors whose queue held an item.
    """
    replayed = 0
    for actor_id in actor_hosts.hosted_actor_ids():
        actor_dl = get_datalayer(actor_id)
        if not actor_dl.inbox_list():
            continue
        replayed += 1
        logger.info(
            "Replaying %d queued inbox item(s) for actor_id=%s at startup"
            " (IE-06-006).",
            len(actor_dl.inbox_list()),
            actor_id,
        )
        try:
            await replay_inbox_queue(actor_dl, actor_id, None, emitter)
        except Exception:
            # The startup boundary: one actor's failed replay must not stop
            # the others' or the server's start.  The attempt rolled back,
            # so its item is still queued (IE-06-005).
            logger.exception(
                "Startup inbox replay raised for actor_id=%s; its items stay"
                " queued for the next replay (IE-06-006).",
                actor_id,
            )
    return replayed
