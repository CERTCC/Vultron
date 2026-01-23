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
Offer Activity Handlers
"""
import logging
from functools import partial

from vultron.api.v2.backend.handlers.activity import ActivityHandler
from vultron.api.v2.data import get_datalayer
from vultron.api.v2.data.store import DataStore
from vultron.as_vocab.base.objects.activities.transitive import as_Offer
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport

logger = logging.getLogger("uvicorn.error")

offer_handler = partial(ActivityHandler, activity_type=as_Offer)


@offer_handler(object_type=VulnerabilityCase)
def offer_case_ownership_transfer(
    actor_id: str,
    activity: as_Offer,
    datalayer: DataStore = get_datalayer(),
) -> None:
    """
    Process an Offer(CaseOwnershipTransfer) activity.

    Args:
        actor_id: The ID of the actor performing the Offer activity.
        activity: The Offer object containing the VulnerabilityCase being offered.
        datalayer: The data layer to use for storing the case. (injected dependency)
    Returns:
        None
    """
    offered_obj = activity.as_object

    # TODO we probably need a specific VulnerabilityCaseOwnershipTransfer object type
    # that provides a minimum context for the ownership transfer rather than the full VulnerabilityCase

    logger.info(
        f"Actor {actor_id} is offering a {offered_obj.as_type}: {offered_obj.name}"
    )
    datalayer.receive_offer(activity)
    datalayer.receive_case(offered_obj)


@offer_handler(object_type=as_Actor)
def recommend_actor_to_case(
    actor_id: str,
    activity: as_Offer,
    datalayer: DataStore = get_datalayer(),
) -> None:
    """
    Process an Offer(Actor) activity.

    Args:
        actor_id: The ID of the actor performing the Offer activity.
        activity: The Offer object containing the Actor being recommended.
        datalayer: The data layer to use for storing the recommendation. (injected dependency)
    Returns:
        None
    """
    offered_obj = activity.as_object

    # TODO the context of the offer should be or resolve to a VulnerabilityCase

    logger.info(
        f"Actor {actor_id} is recommending {offered_obj.as_type} {offered_obj.name}"
    )

    datalayer.receive_offer(activity)


@offer_handler(object_type=VulnerabilityReport)
def rm_submit_report(
    actor_id: str,
    activity: as_Offer,
    datalayer: DataStore = get_datalayer(),
) -> None:
    """
    Process an Offer(VulnerabilityReport) activity.

    Args:
        actor_id: The ID of the actor performing the Offer activity.
        activity: The Offer object containing the VulnerabilityReport being offered.
        datalayer: The data layer to use for storing the report. (injected dependency)
    Returns:
        None
    """
    offered_obj = activity.as_object
    if not isinstance(offered_obj, VulnerabilityReport):
        raise TypeError(
            f"Expected VulnerabilityReport, got {type(offered_obj).__name__}"
        )

    logger.info(
        f"Actor '{activity.actor}' Offers '{actor_id}' a '{offered_obj.as_type}: {offered_obj.name}'"
    )

    _offer_ok = False

    try:
        datalayer.create(offered_obj)
    except ValueError as e:
        logger.error(f"Failed to create nested VulnerabilityReport: {e}")
        return

    try:
        datalayer.create(activity)
    except ValueError as e:
        logger.error(f"Failed to receive offer: {e}")
        return


def main():
    from vultron.api.v2.backend.handlers.registry import (
        ACTIVITY_HANDLER_REGISTRY,
    )

    for k, v in ACTIVITY_HANDLER_REGISTRY.handlers.items():
        for ok, ov in v.items():
            if ok is None:
                print(f"{k.__name__}: None -> {ov.__name__}")
            else:
                print(f"{k.__name__}: {ok.__name__} -> {ov.__name__}")


if __name__ == "__main__":
    main()
