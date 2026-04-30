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

from vultron.wire.as2.vocab.base.objects.activities.intransitive import (
    as_Question,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Announce,
    as_Invite,
    as_Reject,
    as_Remove,
)
from vultron.wire.as2.vocab.examples._base import (
    _COORDINATOR,
    case,
    vendor,
)
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.factories import (
    activate_embargo_activity,
    add_embargo_to_case_activity,
    announce_embargo_activity,
    choose_preferred_embargo_activity,
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
    remove_embargo_from_case_activity,
)


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


def propose_embargo() -> as_Invite:
    embargo = embargo_event()
    _case = case()
    _vendor = vendor()

    activity = em_propose_embargo_activity(
        embargo,
        id_=f"{_case.id_}/embargo_proposals/1",
        actor=_vendor.id_,
        context=_case.id_,
        summary="We propose to embargo case 1 for 90 days.",
    )
    return activity


# TODO this seems less like an API call and more like a poll
def choose_preferred_embargo() -> as_Question:
    embargo_list = [
        embargo_event(90),
        embargo_event(45),
    ]
    _coordinator = _COORDINATOR

    _case = case()
    activity = choose_preferred_embargo_activity(
        id_="https://vultron.example/cases/1/polls/1",
        actor=_coordinator.id_,
        one_of=embargo_list,
        summary="Please accept or reject each of the proposed embargoes.",
        to=f"{_case.id_}/participants",
        context=_case.id_,
    )
    return activity


def accept_embargo() -> as_Accept:
    proposal = propose_embargo()
    _vendor = vendor()
    activity = em_accept_embargo_activity(
        proposal,
        actor=_vendor.id_,
        context=proposal.context,
        to="https://vultron.example/cases/1/participants",
    )
    return activity


def reject_embargo() -> as_Reject:
    proposal = propose_embargo()
    _vendor = vendor()
    activity = em_reject_embargo_activity(
        proposal,
        actor=_vendor.id_,
        context=proposal.context,
        to="https://vultron.example/cases/1/participants",
    )
    return activity


def add_embargo_to_case() -> as_Add:
    _case = case()
    _vendor = vendor()
    activity = add_embargo_to_case_activity(
        embargo_event(90),
        actor=_vendor.id_,
        target=_case.id_,
        to=f"{_case.id_}/participants",
    )
    return activity


def activate_embargo() -> as_Add:
    _case = case()
    _vendor = vendor()
    activity = activate_embargo_activity(
        embargo_event(),
        actor=_vendor.id_,
        target=_case.id_,
        in_reply_to=propose_embargo().id_,
        to=f"{_case.id_}/participants",
    )
    return activity


def announce_embargo() -> as_Announce:
    _vendor = vendor()
    _case = case()

    activity = announce_embargo_activity(
        embargo_event(90),
        actor=_vendor.id_,
        context=_case.id_,
        to=f"{_case.id_}/participants",
    )
    return activity


def remove_embargo() -> as_Remove:
    _vendor = vendor()
    _case = case()
    activity = remove_embargo_from_case_activity(
        embargo_event(90), actor=_vendor.id_, origin=_case.id_
    )
    return activity
