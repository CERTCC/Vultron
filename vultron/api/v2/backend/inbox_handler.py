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

import logging

from pydantic import ValidationError

from vultron.api.v2.backend import handlers  # noqa: F401
from vultron.api.v2.backend.actors import ACTOR_REGISTRY
from vultron.api.v2.backend.handlers.registry import (
    get_activity_handler,
)
from vultron.api.v2.data import get_datalayer
from vultron.as_vocab import VOCABULARY
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.as_vocab.base.objects.base import as_Object
from vultron.as_vocab.base.registry import find_in_vocabulary

logger = logging.getLogger(__name__)

_MAX_REHYDRATION_DEPTH = 5


def rehydrate(obj: as_Object, depth: int = 0) -> as_Object | str:
    """Recursively rehydrate an object if needed. Performs depth-first rehydration to a maximum depth.

    Args:
        obj: The object to rehydrate.
        depth: The current recursion depth (default: 0).
    Returns:
        The rehydrated object of the correct subclass.
    Raises:
        KeyError: If the object type is unrecognized.
        RecursionError: If the maximum rehydration depth is exceeded.
        ValidationError: If the rehydrated object validation fails.
    """
    if depth > _MAX_REHYDRATION_DEPTH:
        raise RecursionError(
            f"Maximum rehydration depth of {_MAX_REHYDRATION_DEPTH} exceeded."
        )

    # short-circuit for strings
    if isinstance(obj, str):
        logger.debug("Object is a string, no rehydration needed.")
        return obj  # type: ignore

    # if object has an `as_object`, rehydrate that first
    # this is the depth-first part
    if hasattr(obj, "as_object"):
        if obj.as_object is not None:
            logger.debug(
                f"Rehydrating nested object in 'as_object' field of {obj.as_type}"
            )
            obj.as_object = rehydrate(obj=obj.as_object, depth=depth + 1)
        else:
            logger.error(f"'as_object' field is None in {obj.as_type}")
            raise ValueError(f"'as_object' field is None in {obj.as_type}")

    # make sure the object has an as_type
    if not hasattr(obj, "as_type"):
        logger.error(f"Object {obj} has no 'as_type' attribute.")
        raise ValueError(f"Object {obj} has no 'as_type' attribute.")

    # now rehydrate the outer object if needed
    cls = find_in_vocabulary(obj.as_type)
    if cls is None:
        logger.error(f"Unknown object type: {obj.as_type}")
        raise KeyError(f"Unknown object type: {obj.as_type}")

    # short-circuit if already rehydrated
    if isinstance(obj, cls):
        logger.debug(
            f"Object already rehydrated as '{obj.__class__.__name__}', skipping rehydration step."
        )
        return obj

    # it's not the right class, re-validate to get the correct subclass
    logger.debug(f"Rehydrating to class {cls.__name__} for type {obj.as_type}")
    try:
        rehydrated = cls.model_validate(obj.model_dump())
    except ValidationError:
        logger.error(f"{cls.__name__} validation failed on {obj}")
        raise

    return rehydrated


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


async def inbox_handler(actor_id: str):
    dl = get_datalayer()

    actor = dl.read(actor_id)
    if actor is None:
        logger.warning(f"Actor {actor_id} not found in inbox_handler.")

    logger.info(f"Processing inbox for actor {actor_id}")
    # Simulate processing each item in the inbox
    err_count = 0
    while actor.inbox.items:
        item = actor.inbox.items.pop(0)

        # in principle because of the POST {actor_id}/inbox method validation,
        # the only items in the inbox should be Activities with registered handlers,
        # but we'll let handle_inbox_item deal with verifying that
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

    return True
