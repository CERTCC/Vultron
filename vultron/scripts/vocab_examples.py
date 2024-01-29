#!/usr/bin/env python
"""
Provides tools for generating examples of Vultron ActivityStreams objects.

Used within the Vultron documentation to provide examples of Vultron ActivityStreams objects.

When run as a script, this module will generate a set of example objects and write them to the docs/reference/examples
directory.
"""
#  Copyright (c) 2024 Carnegie Mellon University and Contributors.
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

from datetime import datetime, timedelta

from vultron.as_vocab.activities.actor import (
    AcceptActorRecommendation,
    RecommendActor,
    RejectActorRecommendation,
)
from vultron.as_vocab.activities.case import (
    AcceptCaseOwnershipTransfer,
    AddNoteToCase,
    AddReportToCase,
    AddStatusToCase,
    CreateCase,
    CreateCaseStatus,
    OfferCaseOwnershipTransfer,
    RejectCaseOwnershipTransfer,
    RmAcceptInviteToCase,
    RmCloseCase,
    RmDeferCase,
    RmEngageCase,
    RmInviteToCase,
    RmRejectInviteToCase,
    UpdateCase,
)
from vultron.as_vocab.activities.case_participant import (
    AddParticipantToCase,
    AddStatusToParticipant,
    CreateParticipant,
    CreateStatusForParticipant,
    RemoveParticipantFromCase,
)
from vultron.as_vocab.activities.embargo import (
    ActivateEmbargo,
    AddEmbargoToCase,
    AnnounceEmbargo,
    ChoosePreferredEmbargo,
    EmAcceptEmbargo,
    EmProposeEmbargo,
    EmRejectEmbargo,
    RemoveEmbargoFromCase,
)
from vultron.as_vocab.activities.report import (
    RmCloseReport,
    RmCreateReport,
    RmInvalidateReport,
    RmReadReport,
    RmSubmitReport,
    RmValidateReport,
)
from vultron.as_vocab.base.base import as_Base
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Create,
    as_Undo,
)
from vultron.as_vocab.base.objects.actors import as_Organization, as_Person
from vultron.as_vocab.base.objects.object_types import as_Event, as_Note
from vultron.as_vocab.objects.case_participant import (
    CaseParticipant,
    CoordinatorParticipant,
    FinderReporterParticipant,
    VendorParticipant,
)
from vultron.as_vocab.objects.case_status import CaseStatus, ParticipantStatus
from vultron.as_vocab.objects.embargo_event import EmbargoEvent
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.bt.embargo_management.states import EM
from vultron.bt.report_management.states import RM
from vultron.case_states.states import CS_pxa, CS_vfd

#  Copyright (c) 2024 Carnegie Mellon University and Contributors.
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

base_url = "https://vultron.example"
user_base_url = f"{base_url}/users"
case_base_url = f"{base_url}/cases"
organization_base_url = f"{base_url}/organizations"
report_base_url = f"{base_url}/reports"


def json2md(obj: as_Base) -> str:
    """
    Given an object with a to_json method, return a markdown-formatted string of the object's JSON.
    Args:
        obj: an object with a to_json method

    Returns:
        a markdown-formatted string of the object's JSON
    """

    # strip out published and updated timestamps
    obj.published = None
    obj.updated = None

    if not hasattr(obj, "to_json"):
        raise TypeError(f"obj must have a to_json method: {obj}")

    s = f"```json\n{obj.to_json(indent=2)}\n```"
    return s


def obj_to_file(obj: as_Base, filename: str) -> None:
    """
    Given an object with a to_json method, write it to a file.
    Args:
        obj: an object with a to_json method
        filename: the file to write to

    Returns:
        None
    """
    # strip out published and updated timestamps
    obj.published = None
    obj.updated = None

    with open(filename, "w") as fp:
        fp.write(obj.to_json(indent=2))


def print_obj(obj: as_Base) -> None:
    """
    Given an object with a to_json method, print it to stdout.
    Args:
        obj: an object with a to_json method

    Returns:
        None
    """
    print(obj.to_json(indent=2))


def finder() -> as_Person:
    """
    Create a finder (Person) object
    Returns:
        an as_Person object
    """
    _finder = as_Person(name="Finn der Vul", as_id=f"{user_base_url}/finn")
    return _finder


def vendor() -> as_Organization:
    """
    Create a vendor (Organization) object
    Returns:
        an as_Organization object
    """
    _vendor = as_Organization(
        name="VendorCo", as_id=f"{organization_base_url}/vendor"
    )
    return _vendor


def report() -> VulnerabilityReport:
    """
    Create a vulnerability report
    Returns:
        a VulnerabilityReport object
    """
    _finder = finder()
    report = VulnerabilityReport(
        name="FDR-8675309",
        as_id=f"{report_base_url}/FDR-8675309",
        content="I found a vulnerability!",
        attributed_to=[
            _finder.as_id,
        ],
    )
    return report


def create_report() -> RmCreateReport:
    """
    In this example, a finder creates a vulnerability report.

    Example:
          >>> RmCreateReport(actor=finder.as_id, as_object=report)
    """
    _finder = finder()
    _report = report()
    activity = RmCreateReport(actor=_finder.as_id, as_object=_report)
    return activity


def submit_report() -> RmSubmitReport:
    _finder = finder()
    _vendor = vendor()
    _report = report()
    activity = RmSubmitReport(
        actor=_finder.as_id, as_object=_report, to=_vendor.as_id
    )
    return activity


def read_report() -> RmReadReport:
    _report = report()
    _vendor = vendor()
    activity = RmReadReport(
        actor=_vendor.as_id,
        as_object=_report.as_id,
        content="We've read the report. We'll get back to you soon.",
    )
    return activity


def validate_report() -> RmValidateReport:
    _report = report()
    _vendor = vendor()
    activity = RmValidateReport(
        actor=_vendor.as_id,
        as_object=_report.as_id,
        content="We've validated the report. We'll be creating a case shortly.",
    )
    return activity


def invalidate_report() -> RmInvalidateReport:
    _report = report()
    _vendor = vendor()
    activity = RmInvalidateReport(
        actor=_vendor.as_id,
        as_object=_report.as_id,
        content="We're declining this report as invalid. If you have a reason we should reconsider, please let us know. Otherwise we'll be closing it shortly.",
    )
    return activity


def close_report() -> RmCloseReport:
    _report = report()
    _vendor = vendor()
    activity = RmCloseReport(
        actor=_vendor.as_id,
        as_object=_report.as_id,
        content="We're closing this report.",
    )
    return activity


def case() -> VulnerabilityCase:
    # create a vulnerability case
    _case = VulnerabilityCase(
        name="VENDOR Case #20991514",
        as_id=f"{case_base_url}/VDR-20991514",
    )
    return _case


def create_case() -> CreateCase:
    _case = case()
    _vendor = vendor()
    _report = report()
    _case.add_report(_report.as_id)
    participant = VendorParticipant(actor=_vendor.as_id, name=_vendor.name)
    _case.add_participant(participant)

    activity = CreateCase(
        actor=_vendor.as_id,
        as_object=_case,
        content="We've created a case from this report.",
        context=_report.as_id,
    )
    return activity


def add_report_to_case() -> AddReportToCase:
    _vendor = vendor()
    _report = report()
    _case = case()

    activity = AddReportToCase(
        actor=_vendor.as_id,
        as_object=_report.as_id,
        target=_case.as_id,
        content="We're adding this report to this case.",
    )
    return activity


def add_vendor_participant_to_case() -> AddParticipantToCase:
    _vendor = vendor()
    _case = case()

    shortname = _vendor.as_id.split("/")[-1]
    _vendor_participant = VendorParticipant(
        as_id=f"{_case.as_id}/participants/{shortname}",
        name=_vendor.name,
        actor=_vendor.as_id,
        context=_case.as_id,
    )

    _pstatus = ParticipantStatus(
        context=_case.as_id,
        actor=_vendor.as_id,
        rm_state=RM.RECEIVED,
        vfd_state=CS_vfd.Vfd,
    )
    _vendor_participant.participant_status = [_pstatus]

    activity = AddParticipantToCase(
        actor=_vendor.as_id,
        as_object=_vendor_participant,
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
        as_id=f"{_case.as_id}/participants/{shortname}",
        name=_finder.name,
        actor=_finder.as_id,
        context=_case.as_id,
    )

    activity = AddParticipantToCase(
        actor=_vendor.as_id,
        as_object=_finder_participant,
        target=_case.as_id,
        content="We're adding the finder as a participant to this case.",
    )
    return activity


def add_coordinator_participant_to_case() -> AddParticipantToCase:
    _vendor = vendor()
    _case = case()

    _coordinator = coordinator()
    shortname = _coordinator.as_id.split("/")[-1]
    _coordinator_participant = CoordinatorParticipant(
        as_id=f"{_case.as_id}/participants/{shortname}",
        name=_coordinator.name,
        actor=_coordinator.as_id,
        context=_case.as_id,
    )

    activity = AddParticipantToCase(
        actor=_vendor.as_id,
        as_object=_coordinator_participant,
        target=_case.as_id,
        content="We're adding the coordinator as a participant to this case.",
    )
    return activity


def engage_case() -> RmEngageCase:
    _vendor = vendor()
    _case = case()

    activity = RmEngageCase(
        actor=_vendor.as_id,
        as_object=_case.as_id,
        content="We're engaging this case.",
    )
    return activity


def close_case() -> RmCloseCase:
    _vendor = vendor()
    _case = case()

    activity = RmCloseCase(
        actor=_vendor.as_id,
        as_object=_case.as_id,
        content="We're closing this case.",
    )
    return activity


def defer_case() -> RmDeferCase:
    _vendor = vendor()
    _case = case()

    activity = RmDeferCase(
        actor=_vendor.as_id,
        as_object=_case.as_id,
        content="We're deferring this case.",
    )
    return activity


def reengage_case() -> as_Undo:
    _vendor = vendor()
    _case = case()
    _deferral = defer_case()

    activity = as_Undo(
        actor=_vendor.as_id,
        as_object=_deferral,
        content="We're reengaging this case.",
        context=_case.as_id,
    )
    return activity


def note() -> as_Note:
    _case = case()
    _note = as_Note(
        name="Note",
        as_id=f"{base_url}/notes/1",
        content="This is a note.",
        context=_case.as_id,
    )
    return _note


def add_note_to_case() -> AddNoteToCase:
    _finder = finder()
    _case = case()
    _note = note()
    _note.context = _case.as_id

    activity = AddNoteToCase(
        actor=_finder.as_id,
        as_object=_note,
        target=_case.as_id,
    )

    return activity


def coordinator() -> as_Organization:
    _coordinator = as_Organization(
        name="Coordinator LLC", as_id=f"{organization_base_url}/coordinator"
    )
    return _coordinator


def accept_case_ownership_transfer() -> AcceptCaseOwnershipTransfer:
    _case = case()
    _coordinator = coordinator()
    _vendor = vendor()
    _activity = AcceptCaseOwnershipTransfer(
        actor=_coordinator.as_id,
        as_object=_case,
        origin=_vendor.as_id,
        content=f"We're accepting your offer to transfer ownership of case {_case.name} to us.",
    )
    return _activity


def offer_case_ownership_transfer() -> OfferCaseOwnershipTransfer:
    _vendor = vendor()
    _case = case()
    _coordinator = coordinator()
    _activity = OfferCaseOwnershipTransfer(
        actor=_vendor.as_id,
        as_object=_case,
        target=_coordinator.as_id,
        content=f"We're offering to transfer ownership of case {_case.name} to you.",
    )
    return _activity


def reject_case_ownership_transfer() -> RejectCaseOwnershipTransfer:
    _case = case()
    _coordinator = coordinator()
    _vendor = vendor()
    _activity = RejectCaseOwnershipTransfer(
        actor=_coordinator.as_id,
        as_object=_case,
        origin=_vendor.as_id,
        content=f"We're declining your offer to transfer ownership of case {_case.name} to us.",
    )
    return _activity


def update_case() -> UpdateCase:
    _case = case()
    _vendor = vendor()

    _activity = UpdateCase(
        actor=_vendor.as_id,
        as_object=_case.as_id,
        content="We're updating the case to reflect a transfer of ownership.",
    )
    return _activity


def recommend_actor() -> RecommendActor:
    _case = case()
    _finder = finder()
    _vendor = vendor()
    _coordinator = coordinator()
    _activity = RecommendActor(
        actor=_finder.as_id,
        as_object=_coordinator.as_id,
        context=_case.as_id,
        target=_case.as_id,
        to=_vendor.as_id,
        content=f"I'm recommending we add {_coordinator.name} to the case.",
    )
    return _activity


def accept_actor_recommendation() -> AcceptActorRecommendation:
    _vendor = vendor()
    _coordinator = coordinator()
    _finder = finder()
    _case = case()
    _activity = AcceptActorRecommendation(
        actor=_vendor.as_id,
        as_object=_coordinator.as_id,
        context=_case.as_id,
        target=_case.as_id,
        to=_finder.as_id,
        content=f"We're accepting your recommendation to add {_coordinator.name} to the case. "
        "We'll reach out to them shortly.",
    )
    return _activity


def reject_actor_recommendation() -> RejectActorRecommendation:
    _vendor = vendor()
    _coordinator = coordinator()
    _finder = finder()
    _case = case()
    _activity = RejectActorRecommendation(
        actor=_vendor.as_id,
        as_object=_coordinator.as_id,
        context=_case.as_id,
        target=_case.as_id,
        to=_finder.as_id,
        content=f"We're declining your recommendation to add {_coordinator.name} to the case. Thanks anyway.",
    )
    return _activity


def rm_invite_to_case() -> RmInviteToCase:
    _vendor = vendor()
    _coordinator = coordinator()
    _case = case()
    _activity = RmInviteToCase(
        as_id=f"{_case.as_id}/invitation/1",
        actor=_vendor.as_id,
        as_object=_coordinator.as_id,
        target=_case.as_id,
        to=_coordinator.as_id,
        content=f"We're inviting you to participate in {_case.name}.",
    )
    return _activity


def accept_invite_to_case() -> RmAcceptInviteToCase:
    _vendor = vendor()
    _coordinator = coordinator()
    _case = case()
    _activity = RmAcceptInviteToCase(
        actor=_coordinator.as_id,
        as_object=_case.as_id,
        to=_vendor.as_id,
        in_reply_to=rm_invite_to_case().as_id,
        content=f"We're accepting your invitation to participate in {_case.name}.",
    )
    return _activity


def reject_invite_to_case() -> RmRejectInviteToCase:
    _vendor = vendor()
    _coordinator = coordinator()
    _case = case()
    _activity = RmRejectInviteToCase(
        actor=_coordinator.as_id,
        as_object=_case.as_id,
        to=_vendor.as_id,
        in_reply_to=rm_invite_to_case().as_id,
        content=f"Thanks for the invitation, but we're declining to participate in {_case.name}.",
    )
    return _activity


def create_participant():
    _vendor = vendor()
    _case = case()
    _coordinator = coordinator()
    _coord_participant = CoordinatorParticipant(
        as_id=f"{_case.as_id}/participants/{_coordinator.as_id}",
        name=_coordinator.name,
        actor=_coordinator.as_id,
        context=_case.as_id,
    )
    _activity = CreateParticipant(
        actor=_vendor.as_id,
        as_object=_coord_participant,
        target=_case.as_id,
        content=f"We're adding {_coordinator.name} to the case.",
    )
    return _activity


def case_status() -> CaseStatus:
    status = CaseStatus(
        as_id="https://vultron.example/cases/1/status/1",
        context="https://vultron.example/cases/1",
        em_state=EM.EMBARGO_MANAGEMENT_NONE,
        pxa_state=CS_pxa.pxa,
    )
    return status


def create_case_status():
    actor = vendor()
    status = case_status()
    _case = case()

    activity = CreateCaseStatus(
        actor=actor.as_id,
        as_object=status,
        context=_case.as_id,
    )
    return activity


def case_participant() -> CaseParticipant:
    participant = VendorParticipant(
        as_id="https://vultron.example/cases/1/participants/vendor",
        name="Vendor",
        actor="https://vultron.example/organizations/vendor",
        context="https://vultron.example/cases/1",
        participant_status=[participant_status()],
    )
    return participant


def coordinator_participant() -> CaseParticipant:
    _actor = coordinator()
    _case = case()

    participant = CoordinatorParticipant(
        as_id=f"{_case.as_id}/participants/coordinator",
        name=_actor.name,
        actor=_actor.as_id,
        context=_case.as_id,
    )
    return participant


def participant_status() -> ParticipantStatus:
    status = ParticipantStatus(
        as_id="https://vultron.example/cases/1/participants/vendor/status/1",
        context="https://vultron.example/cases/1/participants/vendor",
        actor="https://vultron.example/organizations/vendor",
        rm_state=RM.RECEIVED,
        vfd_state=CS_vfd.Vfd,
        case_status=case_status(),
    )
    return status


def invite_to_case():
    _case = case()
    _coordinator = coordinator()
    _vendor = vendor()

    activity = RmInviteToCase(
        as_id=f"{_case.as_id}/invitation/1",
        actor=_vendor.as_id,
        as_object=_coordinator.as_id,
        target=_case.as_id,
        to=_coordinator.as_id,
        content=f"We're inviting you to participate in case {_case.name}.",
    )
    return activity


def embargo_event(days: int = 90) -> as_Event:
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
        as_id=f"{_case.as_id}/embargo_events/{end_at.isoformat()}",
        name=f"Embargo for {_case.name}",
        context=_case.as_id,
        start_time=start_at,
        end_time=end_at,
        content=f"We propose to embargo {_case.name} for {days} days.",
    )
    return event


def create_participant_status() -> ParticipantStatus:
    pstatus = participant_status()

    activity = CreateStatusForParticipant(
        actor="https://vultron.example/organizations/vendor",
        as_object=pstatus,
    )
    return activity


def add_status_to_participant() -> AddStatusToParticipant:
    pstatus = participant_status()

    activity = AddStatusToParticipant(
        actor="https://vultron.example/organizations/vendor",
        as_object=pstatus,
        target="https://vultron.example/cases/1/participants/vendor",
    )
    return activity


def remove_participant_from_case():
    _vendor = vendor()
    _case = case()
    coord_p = coordinator_participant()
    activity = RemoveParticipantFromCase(
        actor=_vendor.as_id,
        as_object=coord_p.as_id,
        origin=_case.as_id,
        summary="Vendor is removing the coordinator from the case.",
    )
    return activity


def propose_embargo() -> EmProposeEmbargo:
    embargo = embargo_event()

    activity = EmProposeEmbargo(
        actor="https://vultron.example/organizations/vendor",
        as_object=embargo,
        target=embargo.context,
        summary="We propose to embargo case 1 for 90 days.",
    )
    return activity


def choose_preferred_embargo() -> ChoosePreferredEmbargo:
    embargo_list = [
        embargo_event(90),
        embargo_event(45),
    ]

    _case = case()
    activity = ChoosePreferredEmbargo(
        as_id="https://vultron.example/cases/1/polls/1",
        actor="https://vultron.example/organizations/coordinator",
        one_of=embargo_list,
        summary="Please accept or reject each of the proposed embargoes.",
        to=f"{_case.as_id}/participants",
        context=_case.as_id,
    )
    return activity


def accept_embargo() -> EmAcceptEmbargo:
    question = choose_preferred_embargo()
    _vendor = vendor()
    activity = EmAcceptEmbargo(
        actor=_vendor.as_id,
        as_object=embargo_event(90),
        context="https://vultron.example/cases/1",
        in_reply_to=question.as_id,
        to="https://vultron.example/cases/1/participants",
    )
    return activity


def reject_embargo() -> EmRejectEmbargo:
    question = choose_preferred_embargo()
    activity = EmRejectEmbargo(
        actor="https://vultron.example/organizations/vendor",
        as_object=embargo_event(45),
        context="https://vultron.example/cases/1",
        in_reply_to=question.as_id,
        to="https://vultron.example/cases/1/participants",
    )
    return activity


def add_embargo_to_case() -> AddEmbargoToCase:
    _case = case()
    _vendor = vendor()
    activity = AddEmbargoToCase(
        actor=_vendor.as_id,
        as_object=embargo_event(90),
        target=_case.as_id,
        to=f"{_case.as_id}/participants",
    )
    return activity


def activate_embargo() -> ActivateEmbargo:
    _case = case()
    _vendor = vendor()
    activity = ActivateEmbargo(
        actor=_vendor.as_id,
        as_object=propose_embargo().as_object,
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
        as_object=embargo_event(90),
        context=_case.as_id,
        to=f"{_case.as_id}/participants",
    )
    return activity


def remove_embargo() -> RemoveEmbargoFromCase:
    _vendor = vendor()
    _case = case()
    activity = RemoveEmbargoFromCase(
        actor=_vendor.as_id,
        as_object=embargo_event(90),
        origin=_case.as_id,
    )
    return activity


def add_status_to_case() -> AddStatusToCase:
    _vendor = vendor()
    _case = case()
    _status = case_status()
    activity = AddStatusToCase(
        actor=_vendor.as_id,
        as_object=_status,
        target=_case.as_id,
    )
    return activity


def create_note():
    _case = case()
    _note = note()
    activity = as_Create(
        actor="https://vultron.example/organizations/vendor",
        as_object=_note,
        target=_case.as_id,
    )
    return activity


def main():
    outdir = "../../docs/reference/examples"
    print(f"Generating examples to: {outdir}")

    # ensure the output directory exists
    from pathlib import Path

    Path(outdir).mkdir(parents=True, exist_ok=True)

    # create a finder (Person) object
    _finder = finder()
    obj_to_file(_finder, f"{outdir}/finder.json")

    # create a vendor (Organization) object
    _vendor = vendor()
    obj_to_file(_vendor, f"{outdir}/vendor.json")

    # create a vulnerability _report
    _report = report()
    obj_to_file(_report, f"{outdir}/vulnerability_report.json")

    # activity: finder creates _report
    activity = create_report()
    obj_to_file(activity, f"{outdir}/create_report.json")

    # activity: finder submits _report to vendor
    activity = submit_report()
    obj_to_file(activity, f"{outdir}/submit_report.json")

    # activity: vendor reads _report
    activity = read_report()
    obj_to_file(activity, f"{outdir}/read_report.json")

    # activity: vendor validates _report
    activity = validate_report()
    obj_to_file(activity, f"{outdir}/validate_report.json")

    # activity: vendor invalidates _report
    activity = invalidate_report()
    obj_to_file(activity, f"{outdir}/invalidate_report.json")

    # activity: vendor closes _report
    activity = close_report()
    obj_to_file(activity, f"{outdir}/close_report.json")

    # case object
    _case = case()
    obj_to_file(_case, f"{outdir}/vulnerability_case.json")

    # activity: vendor creates case from _report
    activity = create_case()
    obj_to_file(activity, f"{outdir}/create_case.json")

    # activity: vendor adds _report to case
    activity = add_report_to_case()
    obj_to_file(activity, f"{outdir}/add_report_to_case.json")

    # activity: vendor adds self as participant to case
    activity = add_vendor_participant_to_case()

    participant = activity.as_object
    obj_to_file(participant, f"{outdir}/vendor_participant.json")
    obj_to_file(activity, f"{outdir}/add_vendor_participant_to_case.json")

    # activity: vendor adds finder as participant to case
    activity = add_finder_participant_to_case()
    participant = activity.as_object
    obj_to_file(participant, f"{outdir}/finder_participant.json")
    obj_to_file(activity, f"{outdir}/add_finder_participant_to_case.json")

    # activity: vendor engages case
    activity = engage_case()
    obj_to_file(activity, f"{outdir}/engage_case.json")

    # activity: vendor closes case
    activity = close_case()
    obj_to_file(activity, f"{outdir}/close_case.json")

    # activity: vendor defers case
    activity = defer_case()
    obj_to_file(activity, f"{outdir}/defer_case.json")

    # activity: vendor reengages case
    activity = reengage_case()
    obj_to_file(activity, f"{outdir}/reengage_case.json")

    # activity: add note to case
    activity = add_note_to_case()
    obj_to_file(activity, f"{outdir}/add_note_to_case.json")

    _coordinator = coordinator()
    obj_to_file(_coordinator, f"{outdir}/coordinator.json")

    # activity: offer case ownership transfer
    activity = offer_case_ownership_transfer()
    obj_to_file(activity, f"{outdir}/offer_case_ownership_transfer.json")

    # activity: accept case ownership transfer
    activity = accept_case_ownership_transfer()
    obj_to_file(activity, f"{outdir}/accept_case_ownership_transfer.json")

    # activity: reject case ownership transfer
    activity = reject_case_ownership_transfer()
    obj_to_file(activity, f"{outdir}/reject_case_ownership_transfer.json")

    # activity: update case
    activity = update_case()
    obj_to_file(activity, f"{outdir}/update_case.json")

    # recommend actor
    activity = recommend_actor()
    obj_to_file(activity, f"{outdir}/recommend_actor.json")

    # accept actor recommendation
    activity = accept_actor_recommendation()
    obj_to_file(activity, f"{outdir}/accept_actor_recommendation.json")

    # reject actor recommendation
    activity = reject_actor_recommendation()
    obj_to_file(activity, f"{outdir}/reject_actor_recommendation.json")

    # rm_invite_to_case
    activity = rm_invite_to_case()
    obj_to_file(activity, f"{outdir}/invite_to_case.json")

    # rm_accept_invite_to_case
    activity = accept_invite_to_case()
    obj_to_file(activity, f"{outdir}/accept_invite_to_case.json")

    # rm_reject_invite_to_case
    activity = reject_invite_to_case()
    obj_to_file(activity, f"{outdir}/reject_invite_to_case.json")

    # create participant
    activity = create_participant()
    obj_to_file(activity, f"{outdir}/create_participant.json")

    _case_status = case_status()
    obj_to_file(_case_status, f"{outdir}/case_status.json")

    _create_case_status = create_case_status()
    obj_to_file(_create_case_status, f"{outdir}/create_case_status.json")

    _add_status_to_case = add_status_to_case()
    obj_to_file(_add_status_to_case, f"{outdir}/add_status_to_case.json")

    _participant_status = participant_status()
    obj_to_file(_participant_status, f"{outdir}/participant_status.json")

    _case_participant = case_participant()
    obj_to_file(_case_participant, f"{outdir}/case_participant.json")

    _embargo_event = embargo_event()
    obj_to_file(_embargo_event, f"{outdir}/embargo_event.json")

    _invite_to_case = invite_to_case()
    obj_to_file(_invite_to_case, f"{outdir}/invite_to_case.json")

    _create_participant_status = create_participant_status()
    obj_to_file(
        _create_participant_status, f"{outdir}/create_participant_status.json"
    )

    _add_status_to_participant = add_status_to_participant()
    obj_to_file(
        _add_status_to_participant, f"{outdir}/add_status_to_participant.json"
    )

    _remove_participant_from_case = remove_participant_from_case()
    obj_to_file(
        _remove_participant_from_case,
        f"{outdir}/remove_participant_from_case.json",
    )

    _propose_embargo = propose_embargo()
    obj_to_file(_propose_embargo, f"{outdir}/propose_embargo.json")

    _choose_preferred_embargo = choose_preferred_embargo()
    obj_to_file(
        _choose_preferred_embargo, f"{outdir}/choose_preferred_embargo.json"
    )

    _accept_embargo = accept_embargo()
    obj_to_file(_accept_embargo, f"{outdir}/accept_embargo.json")

    _reject_embargo = reject_embargo()
    obj_to_file(_reject_embargo, f"{outdir}/reject_embargo.json")

    _add_embargo_to_case = add_embargo_to_case()
    obj_to_file(_add_embargo_to_case, f"{outdir}/add_embargo_to_case.json")

    _activate_embargo = activate_embargo()
    obj_to_file(_activate_embargo, f"{outdir}/activate_embargo.json")

    _announce_embargo = announce_embargo()
    obj_to_file(_announce_embargo, f"{outdir}/announce_embargo.json")

    _remove_embargo = remove_embargo()
    obj_to_file(_remove_embargo, f"{outdir}/remove_embargo.json")

    _create_note = create_note()
    obj_to_file(_create_note, f"{outdir}/create_note.json")


if __name__ == "__main__":
    main()
