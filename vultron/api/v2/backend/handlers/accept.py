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

"""
Accept Activity Handlers
"""
import logging
from functools import partial

from vultron.api.v2.backend.handlers.activity import ActivityHandler
from vultron.api.v2.data import get_datalayer
from vultron.api.v2.data.enums import OfferStatusEnum
from vultron.api.v2.data.rehydration import rehydrate
from vultron.api.v2.data.status import OfferStatus, set_status, ReportStatus
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Invite,
    as_Create,
)
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.embargo_event import EmbargoEvent
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.bt.report_management.states import RM

logger = logging.getLogger("uvicorn.error")

accept_handler = partial(ActivityHandler, activity_type=as_Accept)


@accept_handler(object_type=as_Offer)
def accept_offer_handler(actor_id: str, activity: as_Accept):
    """
    Handle Accept Offer Activity
    """
    accepted_obj = activity.as_object

    logger.info(f"Actor {actor_id} accepts Offer: {accepted_obj.name}")

    # TODO implement business logic
    # if the offer contains an Actor, it's an AcceptActorRecommendation
    # if the offer contains a VulnerabilityCase, it's an AcceptCaseOwnershipTransfer
    # if the offer contains a VulnerabilityReport, it's an RmValidateReport

    offer_referent = accepted_obj.as_object

    if isinstance(offer_referent, as_Actor):
        accept_actor_recommendation(actor_id, activity)
    elif isinstance(offer_referent, VulnerabilityCase):
        accept_case_ownership_transfer(actor_id, activity)
    elif isinstance(offer_referent, VulnerabilityReport):
        rm_validate_report(activity)
    else:
        logger.warning(
            f"Offer referent type {offer_referent.__class__.__name__} not handled"
        )


# - AcceptActorRecommendation
def accept_actor_recommendation(actor_id: str, activity: as_Accept):
    """
    Handle Accept Actor Recommendation Activity
    """
    accepted_obj = activity.as_object
    # NOTE: you Accept the OFFER activity that contains the Actor, not the Actor itself

    logger.info(
        f"Actor {actor_id} accepts Actor recommendation: {accepted_obj.name}"
    )

    # TODO implement business logic


# - AcceptCaseOwnershipTransfer
def accept_case_ownership_transfer(actor_id: str, activity: as_Accept):
    """
    Handle Accept Case Ownership Transfer Activity
    """
    accepted_obj = activity.as_object
    # NOTE: you Accept the OFFER activity that contains the new Owner Actor, not the Actor itself

    logger.info(
        f"Actor {actor_id} accepts Case Ownership Transfer to: {accepted_obj.name}"
    )

    # TODO implement business logic


@accept_handler(object_type=as_Invite)
def accept_invite_handler(actor_id: str, activity: as_Accept):
    """
    Handle Accept Invite Activity
    """
    accepted_obj = activity.as_object

    logger.info(f"Actor {actor_id} accepts Invite: {accepted_obj.name}")

    # TODO implement business logic
    # if the invite contains an Embargo, it's an EmAcceptEmbargo
    # if the invite contains a VulnerabilityCase, it's an RmAccceptInviteToCase

    invite_referent = accepted_obj.as_object

    if isinstance(invite_referent, EmbargoEvent):
        em_accept_embargo(actor_id, activity)
    elif isinstance(invite_referent, VulnerabilityCase):
        rm_accept_invite_to_case(actor_id, activity)
    else:
        logger.warning(
            f"Invite referent type {invite_referent.__class__.__name__} not handled"
        )


# - EmAcceptEmbargo
def em_accept_embargo(actor_id: str, activity: as_Accept):
    """
    Handle Accept Embargo Activity
    """
    accepted_obj = activity.as_object
    # NOTE: you Accept the INVITE activity that contains the Embargo, not the Embargo itself

    logger.info(f"Actor {actor_id} accepts Embargo: {accepted_obj.name}")

    # TODO implement business logic


# - RmAccceptInviteToCase
def rm_accept_invite_to_case(actor_id: str, activity: as_Accept):
    """
    Handle Accept Invite to Case Activity
    """
    accepted_obj = activity.as_object
    # NOTE: you Accept the INVITE activity that contains the Case, not the Case itself

    logger.info(
        f"Actor {actor_id} accepts Invite to Case: {accepted_obj.name}"
    )

    # TODO implement business logic


# - RmValidateReport
def rm_validate_report(activity: as_Accept):
    """
    Handle Accept Vulnerability Report Activity
    """
    accepted_offer = rehydrate(activity.as_object)
    accepted_report = rehydrate(accepted_offer.as_object)
    actor = rehydrate(activity.actor)
    actor_id = actor.as_id

    logger.info(
        f"Actor {actor_id} accepts VulnerabilityReport: {accepted_offer.name}"
    )

    offer_status = OfferStatus(
        object_type=accepted_offer.as_type,
        object_id=accepted_offer.as_id,
        status=OfferStatusEnum.ACCEPTED,
        actor_id=actor_id,
    )
    set_status(offer_status)

    report_status = ReportStatus(
        object_type=accepted_report.as_type,
        object_id=accepted_report.as_id,
        status=RM.VALID,
        actor_id=actor_id,
    )
    set_status(report_status)

    # create a case
    case = VulnerabilityCase(
        name=f"Case for Report {accepted_report.as_id}",
        vulnerability_reports=[accepted_report],
        attributed_to=actor.as_id,
    )
    dl = get_datalayer()
    dl.create(case)

    create_case = as_Create(
        actor=actor.as_id,
        object=case,
    )


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
