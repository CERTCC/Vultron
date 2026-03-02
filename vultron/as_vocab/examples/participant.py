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

from vultron.as_vocab.activities.case import (
    RmAcceptInviteToCase,
    RmInviteToCase,
    RmRejectInviteToCase,
)
from vultron.as_vocab.activities.case_participant import (
    AddParticipantToCase,
    RemoveParticipantFromCase,
)
from vultron.as_vocab.base.objects.activities.transitive import as_Create
from vultron.as_vocab.examples._base import (
    _CASE,
    _COORDINATOR,
    _FINDER,
    _VENDOR,
    case,
    finder,
    vendor,
)
from vultron.as_vocab.examples.status import case_status, participant_status
from vultron.as_vocab.objects.case_participant import (
    CaseParticipant,
    CoordinatorParticipant,
    FinderReporterParticipant,
    VendorParticipant,
)
from vultron.as_vocab.objects.case_status import ParticipantStatus
from vultron.bt.report_management.states import RM
from vultron.case_states.states import CS_vfd


def add_vendor_participant_to_case() -> AddParticipantToCase:
    _vendor = vendor()
    _case = case()

    shortname = _vendor.as_id.split("/")[-1]
    _vendor_participant = VendorParticipant(
        id=f"{_case.as_id}/participants/{shortname}",
        name=_vendor.name,
        attributed_to=_vendor.as_id,
        context=_case.as_id,
    )

    _pstatus = ParticipantStatus(
        context=_case.as_id,
        attributed_to=_vendor.as_id,
        rm_state=RM.RECEIVED,
        vfd_state=CS_vfd.Vfd,
    )
    _vendor_participant.participant_statuses = [_pstatus]

    activity = AddParticipantToCase(
        actor=_vendor.as_id,
        object=_vendor_participant,
        target=_case.as_id,
        content="We're adding ourselves as a participant to this case.",
    )
    return activity


def add_finder_participant_to_case() -> AddParticipantToCase:
    _vendor = vendor()
    _case = case()

    _finder = finder()
    shortname = _finder.as_id.split("/")[-1]
    _finder_participant = FinderReporterParticipant(
        id=f"{_case.as_id}/participants/{shortname}",
        name=_finder.name,
        attributed_to=_finder.as_id,
        context=_case.as_id,
    )

    activity = AddParticipantToCase(
        actor=_vendor.as_id,
        object=_finder_participant,
        target=_case.as_id,
        content="We're adding the finder as a participant to this case.",
    )
    return activity


def add_coordinator_participant_to_case() -> AddParticipantToCase:
    _vendor = vendor()
    _case = case()

    _coordinator = _COORDINATOR
    shortname = _coordinator.as_id.split("/")[-1]
    _coordinator_participant = CoordinatorParticipant(
        id=f"{_case.as_id}/participants/{shortname}",
        name=_coordinator.name,
        attributed_to=_coordinator.as_id,
        context=_case.as_id,
    )

    activity = AddParticipantToCase(
        actor=_vendor.as_id,
        object=_coordinator_participant,
        target=_case.as_id,
        content="We're adding the coordinator as a participant to this case.",
    )
    return activity


def rm_invite_to_case() -> RmInviteToCase:
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _case = case()
    _activity = RmInviteToCase(
        id=f"{_case.as_id}/invitation/1",
        actor=_vendor.as_id,
        object=_coordinator.as_id,
        target=_case.as_id,
        to=_coordinator.as_id,
        content=f"We're inviting you to participate in {_case.name}.",
    )
    return _activity


def accept_invite_to_case() -> RmAcceptInviteToCase:
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _case = case()
    _invite = rm_invite_to_case()
    _activity = RmAcceptInviteToCase(
        actor=_coordinator.as_id,
        object=_invite,
        to=_vendor.as_id,
        content=f"We're accepting your invitation to participate in {_case.name}.",
    )
    return _activity


def reject_invite_to_case() -> RmRejectInviteToCase:
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _case = case()
    _invite = rm_invite_to_case()
    _activity = RmRejectInviteToCase(
        actor=_coordinator.as_id,
        object=_invite,
        to=_vendor.as_id,
        content=f"Thanks for the invitation, but we're declining to participate in {_case.name}.",
    )
    return _activity


def create_participant():
    _vendor = vendor()
    _case = case()
    _coordinator = _COORDINATOR
    _coord_participant = CoordinatorParticipant(
        id=f"{_case.as_id}/participants/{_coordinator.as_id}",
        name=_coordinator.name,
        attributed_to=_coordinator.as_id,
        context=_case.as_id,
    )
    _activity = as_Create(
        actor=_vendor.as_id,
        object=_coord_participant,
        context=_case.as_id,
        content=f"We're adding {_coordinator.name} to the case.",
    )
    return _activity


def case_participant() -> CaseParticipant:
    participant = VendorParticipant(
        id="https://vultron.example/cases/1/participants/vendor",
        name="Vendor",
        attributed_to="https://vultron.example/organizations/vendor",
        context="https://vultron.example/cases/1",
        participant_status=[participant_status()],
    )
    return participant


def coordinator_participant() -> CaseParticipant:
    _actor = _COORDINATOR
    _case = case()

    participant = CoordinatorParticipant(
        id=f"{_case.as_id}/participants/coordinator",
        name=_actor.name,
        attributed_to=_actor.as_id,
        context=_case.as_id,
    )
    return participant


def invite_to_case():
    _case = case()
    _coordinator = _COORDINATOR
    _vendor = vendor()

    activity = RmInviteToCase(
        id=f"{_case.as_id}/invitation/1",
        actor=_vendor.as_id,
        object=_coordinator.as_id,
        target=_case.as_id,
        to=_coordinator.as_id,
        content=f"We're inviting you to participate in case {_case.name}.",
    )
    return activity


def remove_participant_from_case():
    _vendor = vendor()
    _case = case()
    coord_p = coordinator_participant()
    activity = RemoveParticipantFromCase(
        actor=_vendor.as_id,
        object=coord_p.as_id,
        origin=_case.as_id,
        summary="Vendor is removing the coordinator from the case.",
    )
    return activity
