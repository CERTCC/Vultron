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


def rehydrate(activity: as_Activity) -> as_Activity:
    """Rehydrate an activity object if needed.

    Args:
        activity: The activity object to rehydrate.
    Returns:
        The rehydrated activity object of the correct subclass.
    Raises:
        ValidationError: If the activity type is unknown.
    """
    try:
        cls = VOCABULARY.activities.get(activity.as_type, as_Activity)
    except ValidationError:
        logger.error(f"{cls.__name__} validation failed on {activity}")
        raise

    return cls.model_validate(activity.model_dump())


def handle_create(actor_id: str, obj: as_Create):
    logger.info(f"Actor {actor_id} received Create activity: {obj.name}")

    # what are we creating?
    created_obj = obj.object
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


def handle_offer(actor_id: str, obj: as_Offer):
    logger.info(f"Actor {actor_id} received Offer activity: {obj.name}")


def handle_unknown(actor_id: str, obj: as_Activity):
    logger.warning(
        f"Actor {actor_id} received unknown Activity type {obj.as_type}: {obj.name}"
    )


def handle_inbox_item(actor_id: str, obj: as_Activity):
    logger.info(f"Processing item {obj.name} for actor {actor_id}")

    logger.info(
        f"Validated object:\n{obj.model_dump_json(indent=2,exclude_none=True)}"
    )
    # we should only be receiving Activities in the inbox.
    if obj.as_type not in VOCABULARY.activities:
        raise ValueError(
            f"Invalid object type {obj.as_type} in inbox for actor {actor_id}"
        )

    # noinspection PyTypeChecker
    obj = rehydrate(obj)

    match obj.__class__.__name__:
        # add hints for each Activity type we want to handle
        case as_Create.__name__:
            obj: as_Create
            handle_create(actor_id, obj)
        case as_Offer.__name__:
            obj: as_Offer
            handle_offer(actor_id, obj)
        case _:
            handle_unknown(actor_id, obj)


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

        # in principle because of the POST {actor_id}/inbox method validation,
        # the only items in the inbox should be Activities
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

        await asyncio.sleep(0.1)  # Simulate some processing time

    return True
