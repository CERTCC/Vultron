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

from vultron.wire.as2.vocab.activities.case import (
    RmAcceptInviteToCaseActivity,
    RmInviteToCaseActivity,
    RmRejectInviteToCaseActivity,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    AddParticipantToCaseActivity,
    RemoveParticipantFromCaseActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.examples._base import (
    _COORDINATOR,
    case,
    finder,
    vendor,
)
from vultron.wire.as2.vocab.examples.status import (
    participant_status,
)
from vultron.wire.as2.vocab.objects.case_participant import (
    CaseParticipant,
    CoordinatorParticipant,
    FinderReporterParticipant,
    VendorParticipant,
)
from vultron.wire.as2.vocab.objects.case_status import ParticipantStatus
from vultron.core.states.rm import RM
from vultron.core.states.cs import CS_vfd


def add_vendor_participant_to_case() -> AddParticipantToCaseActivity:
    _vendor = vendor()
    _case = case()

    shortname = _vendor.id_.split("/")[-1]
    _vendor_participant = VendorParticipant(
        id_=f"{_case.id_}/participants/{shortname}",
        name=_vendor.name,
        attributed_to=_vendor.id_,
        context=_case.id_,
    )

    _pstatus = ParticipantStatus(
        context=_case.id_,
        attributed_to=_vendor.id_,
        rm_state=RM.RECEIVED,
        vfd_state=CS_vfd.Vfd,
    )
    _vendor_participant.participant_statuses = [_pstatus]

    activity = AddParticipantToCaseActivity(
        actor=_vendor.id_,
        object_=_vendor_participant,
        target=_case.id_,
        content="We're adding ourselves as a participant to this case.",
    )
    return activity


def add_finder_participant_to_case() -> AddParticipantToCaseActivity:
    _vendor = vendor()
    _case = case()

    _finder = finder()
    shortname = _finder.id_.split("/")[-1]
    _finder_participant = FinderReporterParticipant(
        id_=f"{_case.id_}/participants/{shortname}",
        name=_finder.name,
        attributed_to=_finder.id_,
        context=_case.id_,
    )

    activity = AddParticipantToCaseActivity(
        actor=_vendor.id_,
        object_=_finder_participant,
        target=_case.id_,
        content="We're adding the finder as a participant to this case.",
    )
    return activity


def add_coordinator_participant_to_case() -> AddParticipantToCaseActivity:
    _vendor = vendor()
    _case = case()

    _coordinator = _COORDINATOR
    shortname = _coordinator.id_.split("/")[-1]
    _coordinator_participant = CoordinatorParticipant(
        id_=f"{_case.id_}/participants/{shortname}",
        name=_coordinator.name,
        attributed_to=_coordinator.id_,
        context=_case.id_,
    )

    activity = AddParticipantToCaseActivity(
        actor=_vendor.id_,
        object_=_coordinator_participant,
        target=_case.id_,
        content="We're adding the coordinator as a participant to this case.",
    )
    return activity


def rm_invite_to_case() -> RmInviteToCaseActivity:
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _case = case()
    _activity = RmInviteToCaseActivity(
        id_=f"{_case.id_}/invitation/1",
        actor=_vendor.id_,
        object_=_coordinator,
        target=_case.id_,
        to=_coordinator.id_,
        content=f"We're inviting you to participate in {_case.name}.",
    )
    return _activity


def accept_invite_to_case() -> RmAcceptInviteToCaseActivity:
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _case = case()
    _invite = rm_invite_to_case()
    _activity = RmAcceptInviteToCaseActivity(
        actor=_coordinator.id_,
        object_=_invite,
        to=_vendor.id_,
        content=f"We're accepting your invitation to participate in {_case.name}.",
    )
    return _activity


def reject_invite_to_case() -> RmRejectInviteToCaseActivity:
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _case = case()
    _invite = rm_invite_to_case()
    _activity = RmRejectInviteToCaseActivity(
        actor=_coordinator.id_,
        object_=_invite,
        to=_vendor.id_,
        content=f"Thanks for the invitation, but we're declining to participate in {_case.name}.",
    )
    return _activity


def create_participant():
    _vendor = vendor()
    _case = case()
    _coordinator = _COORDINATOR
    _coord_participant = CoordinatorParticipant(
        id_=f"{_case.id_}/participants/{_coordinator.id_}",
        name=_coordinator.name,
        attributed_to=_coordinator.id_,
        context=_case.id_,
    )
    _activity = as_Create(
        actor=_vendor.id_,
        object_=_coord_participant,
        context=_case.id_,
        content=f"We're adding {_coordinator.name} to the case.",
    )
    return _activity


def case_participant() -> CaseParticipant:
    participant = VendorParticipant(
        id_="https://vultron.example/cases/1/participants/vendor",
        name="Vendor",
        attributed_to="https://vultron.example/organizations/vendor",
        context="https://vultron.example/cases/1",
        participant_statuses=[participant_status()],
    )
    return participant


def coordinator_participant() -> CaseParticipant:
    _actor = _COORDINATOR
    _case = case()

    participant = CoordinatorParticipant(
        id_=f"{_case.id_}/participants/coordinator",
        name=_actor.name,
        attributed_to=_actor.id_,
        context=_case.id_,
    )
    return participant


def invite_to_case():
    _case = case()
    _coordinator = _COORDINATOR
    _vendor = vendor()

    activity = RmInviteToCaseActivity(
        id_=f"{_case.id_}/invitation/1",
        actor=_vendor.id_,
        object_=_coordinator,
        target=_case.id_,
        to=_coordinator.id_,
        content=f"We're inviting you to participate in case {_case.name}.",
    )
    return activity


def remove_participant_from_case():
    _vendor = vendor()
    _case = case()
    coord_p = coordinator_participant()
    activity = RemoveParticipantFromCaseActivity(
        actor=_vendor.id_,
        object_=coord_p,
        origin=_case.id_,
        summary="Vendor is removing the coordinator from the case.",
    )
    return activity
