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
    ActivateEmbargo,
    AddEmbargoToCase,
    AnnounceEmbargo,
    ChoosePreferredEmbargo,
    EmAcceptEmbargo,
    EmProposeEmbargo,
    EmRejectEmbargo,
    RemoveEmbargoFromCase,
)
from vultron.wire.as2.vocab.examples._base import (
    _COORDINATOR,
    _VENDOR,
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
        id=f"{_case.as_id}/embargo_events/{end_at.isoformat()}",
        name=f"Embargo for {_case.name}",
        context=_case.as_id,
        start_time=start_at,
        end_time=end_at,
        content=f"We propose to embargo {_case.name} for {days} days.",
    )
    return event


def propose_embargo() -> EmProposeEmbargo:
    embargo = embargo_event()
    _case = case()
    _vendor = vendor()

    activity = EmProposeEmbargo(
        id=f"{_case.as_id}/embargo_proposals/1",
        actor=_vendor.as_id,
        object=embargo,
        context=_case.as_id,
        summary="We propose to embargo case 1 for 90 days.",
    )
    return activity


# TODO this seems less like an API call and more like a poll
def choose_preferred_embargo() -> ChoosePreferredEmbargo:
    embargo_list = [
        embargo_event(90),
        embargo_event(45),
    ]
    _coordinator = _COORDINATOR

    _case = case()
    activity = ChoosePreferredEmbargo(
        id="https://vultron.example/cases/1/polls/1",
        actor=_coordinator.as_id,
        one_of=embargo_list,
        summary="Please accept or reject each of the proposed embargoes.",
        to=f"{_case.as_id}/participants",
        context=_case.as_id,
    )
    return activity


def accept_embargo() -> EmAcceptEmbargo:
    proposal = propose_embargo()
    _vendor = vendor()
    activity = EmAcceptEmbargo(
        actor=_vendor.as_id,
        object=proposal,
        context=proposal.context,
        to="https://vultron.example/cases/1/participants",
    )
    return activity


def reject_embargo() -> EmRejectEmbargo:
    proposal = propose_embargo()
    _vendor = vendor()
    activity = EmRejectEmbargo(
        actor=_vendor.as_id,
        object=proposal,
        context=proposal.context,
        to="https://vultron.example/cases/1/participants",
    )
    return activity


def add_embargo_to_case() -> AddEmbargoToCase:
    _case = case()
    _vendor = vendor()
    activity = AddEmbargoToCase(
        actor=_vendor.as_id,
        object=embargo_event(90),
        target=_case.as_id,
        to=f"{_case.as_id}/participants",
    )
    return activity


def activate_embargo() -> ActivateEmbargo:
    _case = case()
    _vendor = vendor()
    activity = ActivateEmbargo(
        actor=_vendor.as_id,
        object=propose_embargo().as_object,
        target=_case.as_id,
        in_reply_to=propose_embargo().as_id,
        to=f"{_case.as_id}/participants",
    )
    return activity


def announce_embargo() -> AnnounceEmbargo:
    _vendor = vendor()
    _case = case()

    activity = AnnounceEmbargo(
        actor=_vendor.as_id,
        object=embargo_event(90),
        context=_case.as_id,
        to=f"{_case.as_id}/participants",
    )
    return activity


def remove_embargo() -> RemoveEmbargoFromCase:
    _vendor = vendor()
    _case = case()
    activity = RemoveEmbargoFromCase(
        actor=_vendor.as_id,
        object=embargo_event(90),
        origin=_case.as_id,
    )
    return activity
