#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

from datetime import datetime, timedelta

from vultron.wire.as2.vocab.activities.embargo import (
    ActivateEmbargoActivity,
    AddEmbargoToCaseActivity,
    AnnounceEmbargoActivity,
    ChoosePreferredEmbargoActivity,
    EmAcceptEmbargoActivity,
    EmProposeEmbargoActivity,
    EmRejectEmbargoActivity,
    RemoveEmbargoFromCaseActivity,
)
from vultron.wire.as2.vocab.examples._base import (
    _COORDINATOR,
    case,
    vendor,
)
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent


def embargo_event(days: int = 90) -> EmbargoEvent:
    start_at = datetime.now().astimezone(tz=None)
    # zero out the seconds and microseconds
    start_at = start_at.replace(second=0, microsecond=0)

    # set end time to 90 days from now, with a time of 00:00:00, in UTC
    end_at = start_at + timedelta(days=days)
    # zero out the time
    end_at = end_at.replace(hour=0, minute=0, second=0, microsecond=0)
    # convert to UTC
    end_at = end_at.astimezone(tz=None)

    _case = case()

    event = EmbargoEvent(
        id_=f"{_case.id_}/embargo_events/{end_at.isoformat()}",
        name=f"Embargo for {_case.name}",
        context=_case.id_,
        start_time=start_at,
        end_time=end_at,
        content=f"We propose to embargo {_case.name} for {days} days.",
    )
    return event


def propose_embargo() -> EmProposeEmbargoActivity:
    embargo = embargo_event()
    _case = case()
    _vendor = vendor()

    activity = EmProposeEmbargoActivity(
        id_=f"{_case.id_}/embargo_proposals/1",
        actor=_vendor.id_,
        object_=embargo,
        context=_case.id_,
        summary="We propose to embargo case 1 for 90 days.",
    )
    return activity


# TODO this seems less like an API call and more like a poll
def choose_preferred_embargo() -> ChoosePreferredEmbargoActivity:
    embargo_list = [
        embargo_event(90),
        embargo_event(45),
    ]
    _coordinator = _COORDINATOR

    _case = case()
    activity = ChoosePreferredEmbargoActivity(
        id_="https://vultron.example/cases/1/polls/1",
        actor=_coordinator.id_,
        one_of=embargo_list,
        summary="Please accept or reject each of the proposed embargoes.",
        to=f"{_case.id_}/participants",
        context=_case.id_,
    )
    return activity


def accept_embargo() -> EmAcceptEmbargoActivity:
    proposal = propose_embargo()
    _vendor = vendor()
    activity = EmAcceptEmbargoActivity(
        actor=_vendor.id_,
        object_=proposal,
        context=proposal.context,
        to="https://vultron.example/cases/1/participants",
    )
    return activity


def reject_embargo() -> EmRejectEmbargoActivity:
    proposal = propose_embargo()
    _vendor = vendor()
    activity = EmRejectEmbargoActivity(
        actor=_vendor.id_,
        object_=proposal,
        context=proposal.context,
        to="https://vultron.example/cases/1/participants",
    )
    return activity


def add_embargo_to_case() -> AddEmbargoToCaseActivity:
    _case = case()
    _vendor = vendor()
    activity = AddEmbargoToCaseActivity(
        actor=_vendor.id_,
        object_=embargo_event(90),
        target=_case.id_,
        to=f"{_case.id_}/participants",
    )
    return activity


def activate_embargo() -> ActivateEmbargoActivity:
    _case = case()
    _vendor = vendor()
    activity = ActivateEmbargoActivity(
        actor=_vendor.id_,
        object_=propose_embargo().object_,
        target=_case.id_,
        in_reply_to=propose_embargo().id_,
        to=f"{_case.id_}/participants",
    )
    return activity


def announce_embargo() -> AnnounceEmbargoActivity:
    _vendor = vendor()
    _case = case()

    activity = AnnounceEmbargoActivity(
        actor=_vendor.id_,
        object_=embargo_event(90),
        context=_case.id_,
        to=f"{_case.id_}/participants",
    )
    return activity


def remove_embargo() -> RemoveEmbargoFromCaseActivity:
    _vendor = vendor()
    _case = case()
    activity = RemoveEmbargoFromCaseActivity(
        actor=_vendor.id_,
        object_=embargo_event(90),
        origin=_case.id_,
    )
    return activity
