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
from functools import wraps
from typing import Callable, TypeVar, cast

from pydantic import ValidationError

from vultron.api.v2.backend.actors import ACTOR_REGISTRY
from vultron.as_vocab import VOCABULARY
from vultron.as_vocab.base.links import as_Link
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Create,
    as_Offer,
)
from vultron.as_vocab.base.objects.object_types import as_Note
from vultron.as_vocab.objects.case_participant import CaseParticipant
from vultron.as_vocab.objects.case_status import CaseStatus, ParticipantStatus
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport

logger = logging.getLogger("uvicorn.error")


AsActivityType = TypeVar("AsActivityType", bound=as_Activity)

ACTIVITY_HANDLERS: dict[
    type[as_Activity], Callable[[str, as_Activity], None]
] = {}


def rehydrate(activity: as_Activity) -> AsActivityType:
    """Rehydrate an activity object if needed.

    Args:
        activity: The activity object to rehydrate.
    Returns:
        The rehydrated activity object of the correct subclass.
    Raises:
        KeyError: If the activity type is unknown.
        ValidationError: If the activity validation fails.
    """
    try:
        cls = VOCABULARY.activities[activity.as_type]
    except KeyError:
        logger.error(f"Unknown activity type: {activity.as_type}")
        raise

    # we have the correct class, now re-validate to get the correct subclass
    try:
        return cls.model_validate(activity.model_dump())
    except ValidationError:
        logger.error(f"{cls.__name__} validation failed on {activity}")
        raise


def activity_handler(
    activity_type: type[AsActivityType],
) -> Callable[
    [Callable[[str, AsActivityType], None]], Callable[[str, as_Activity], None]
]:
    def decorator(
        func: Callable[[str, AsActivityType], None],
    ) -> Callable[[str, as_Activity], None]:
        @wraps(func)
        def wrapper(actor_id: str, obj: AsActivityType):
            if not isinstance(obj, activity_type):
                raise TypeError(
                    f"Handler for {activity_type.__name__} received wrong type: {obj.__class__.__name__}"
                )
            return func(actor_id, cast(AsActivityType, obj))

        ACTIVITY_HANDLERS[activity_type] = wrapper
        return wrapper

    return decorator


@activity_handler(as_Create)
def handle_create(actor_id: str, obj: as_Create):
    logger.info(f"Actor {actor_id} received Create activity: {obj.name}")

    # what are we creating?
    created_obj = obj.as_object
    match created_obj.__class__.__name__:
        case as_Note.__name__:
            logger.info(f"Actor {actor_id} received Note object: {obj.name}")
        case as_Link.__name__:
            logger.info(f"Actor {actor_id} received Link object: {obj.name}")
            # TODO this will need further processing to determine what the link points to
        case VulnerabilityReport.__name__:
            logger.info(
                f"Actor {actor_id} received VulnerabilityReport object: {obj.name}"
            )
        case VulnerabilityCase.__name__:
            logger.info(
                f"Actor {actor_id} received VulnerabilityCase object: {obj.name}"
            )
        case CaseParticipant.__name__:
            logger.info(
                f"Actor {actor_id} received CaseParticipant object: {obj.name}"
            )
        case CaseStatus.__name__:
            logger.info(
                f"Actor {actor_id} received CaseStatus object: {obj.name}"
            )
        case ParticipantStatus.__name__:
            logger.info(
                f"Actor {actor_id} received ParticipantStatus object: {obj.name}"
            )
        case _:
            logger.info(
                f"Actor {actor_id} received Create activity with unknown object type {created_obj.as_type}: {obj.name}"
            )


@activity_handler(as_Offer)
def handle_offer(actor_id: str, obj: as_Offer):
    logger.info(f"Actor {actor_id} received Offer activity: {obj.name}")


def handle_unknown(actor_id: str, obj: as_Activity):
    logger.warning(
        f"Actor {actor_id} received unknown Activity type {obj.as_type}: {obj.name}"
    )


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
    logger.info(f"Processing item {obj.name} for actor {actor_id}")

    logger.info(
        f"Validated object:\n{obj.model_dump_json(indent=2,exclude_none=True)}"
    )
    # we should only be receiving Activities in the inbox.
    if obj.as_type not in VOCABULARY.activities:
        raise ValueError(
            f"Invalid object type {obj.as_type} in inbox for actor {actor_id}"
        )

    rehydrated = rehydrate(obj)
    activity_cls = type(rehydrated)
    handler = ACTIVITY_HANDLERS.get(activity_cls, handle_unknown)
    handler(actor_id, rehydrated)


async def inbox_handler(actor_id: str):
    actor = ACTOR_REGISTRY.get_actor(actor_id)
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
