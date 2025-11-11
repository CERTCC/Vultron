#!/usr/bin/env python
"""
Handler for Reject Activities
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
from functools import partial

from vultron.api.v2.backend.handlers.activity import ActivityHandler
from vultron.api.v2.data import get_datalayer
from vultron.api.v2.data.enums import OfferStatusEnum
from vultron.api.v2.data.rehydration import rehydrate
from vultron.api.v2.data.status import OfferStatus, set_status, ReportStatus
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Reject,
    as_TentativeReject,
    as_Offer,
)
from vultron.bt.report_management.states import RM

logger = logging.getLogger(__name__)

reject_handler = partial(ActivityHandler, activity_type=as_Reject)

tentative_reject_handler = partial(
    ActivityHandler, activity_type=as_TentativeReject
)


@reject_handler(object_type=as_Offer)
def reject_offer(
    actor_id: str,
    activity: as_Reject,
) -> None:
    """
    Handle Reject activity for Offer
    """
    logger.debug(f"Reject offer activity: {activity}")
    datalayer = get_datalayer()
    datalayer.create(activity)

    rejected_offer = activity.as_object
    subject_of_offer = rejected_offer.as_object
    match subject_of_offer.as_type:
        case "VulnerabilityReport":
            rm_close_report(activity)
        case _:
            logger.warning(
                f"Actor {actor_id} rejected offer {rejected_offer.as_id} of an unsupported type {subject_of_offer.as_type}."
            )
    logger.debug(f"Subject of rejected offer: {subject_of_offer}")


def rm_close_report(
    activity: as_Reject,
) -> None:
    """
    Handle Reject activity for VulnerabilityReport
    """

    actor = rehydrate(obj=activity.actor)
    actor_id = actor.as_id
    rejected_offer = rehydrate(activity.as_object)
    subject_of_offer = rehydrate(rejected_offer.as_object)
    logger.info(
        f"Actor {actor_id} rejected offer {rejected_offer.as_id} of a VulnerabilityReport {subject_of_offer.as_id}."
    )

    offer_status = OfferStatus(
        object_type=rejected_offer.as_type,
        object_id=rejected_offer.as_id,
        status=OfferStatusEnum.REJECTED,
        actor_id=actor_id,
    )
    set_status(offer_status)

    report_status = ReportStatus(
        object_type=subject_of_offer.as_type,
        object_id=subject_of_offer.as_id,
        status=RM.CLOSED,
        actor_id=actor_id,
    )
    set_status(report_status)


@tentative_reject_handler(object_type=as_Offer)
def tentative_reject_offer(
    actor_id: str,
    activity: as_TentativeReject,
) -> None:
    """
    Handle TentativeReject activity for Offer
    """
    logger.debug(f"TentativeReject offer activity: {activity}")
    rejected_offer = activity.as_object
    subject_of_offer = rejected_offer.as_object
    match subject_of_offer.as_type:
        case "VulnerabilityReport":
            rm_invalidate_report(activity)
        case _:
            logger.warning(
                f"Actor {actor_id} Tentatively Rejected offer {rejected_offer.as_id} of an unsupported type {subject_of_offer.as_type}."
            )
    logger.debug(f"Subject of tentatively rejected offer: {subject_of_offer}")


def rm_invalidate_report(
    activity: as_TentativeReject,
) -> None:
    """
    Handle TentativeReject activity for VulnerabilityReport
    """
    actor = rehydrate(obj=activity.actor)
    actor_id = actor.as_id
    rejected_offer = activity.as_object
    subject_of_offer = rejected_offer.as_object
    logger.info(
        f"Actor {actor_id} Tentatively Rejected offer {rejected_offer.as_id} of a VulnerabilityReport {subject_of_offer.as_id}."
    )
    status_record = OfferStatus(
        object_type=rejected_offer.as_type,
        object_id=rejected_offer.as_id,
        status=OfferStatusEnum.TENTATIVELY_REJECTED,
        actor_id=actor_id,
    )
    set_status(status_record=status_record)
