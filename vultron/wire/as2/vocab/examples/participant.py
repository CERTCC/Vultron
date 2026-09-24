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

from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Create,
    as_Invite,
    as_Reject,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.examples._base import (
    _COORDINATOR,
    case,
    finder,
    vendor,
)
from vultron.wire.as2.vocab.examples.status import (
    participant_status,
)
from vultron.core.states.cs import CS_vf
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.factories import (
    add_participant_to_case_activity,
    remove_participant_from_case_activity,
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
    rm_reject_invite_to_case_activity,
)
from vultron.core.models.dimensions import (
    RmDimension,
    VfDimension,
)


def _participant_for(
    actor: as_Actor,
    case_roles: list[CVDRole],
    participant_statuses: list[as_ParticipantStatus] | None = None,
) -> as_CaseParticipant:
    """Build the case-participant record wrapping *actor* in the example case.

    ``participant_statuses`` is omitted rather than passed as ``[]`` when the
    caller supplies none, so that ``_init_participant_status_if_empty`` seeds the
    opening status.  A participant with an empty status list has no RM state at
    all, which is not a participant any example should show.

    The distinction only started to matter when ``as_CaseParticipant`` became the
    core class: the wire class seeded in a ``mode="after"`` validator, which ran
    regardless, while core seeds in ``mode="before"`` and — correctly — treats an
    explicit ``[]`` as the caller's decision.  Passing the key unconditionally was
    therefore silently suppressing the seed.
    """
    _case = case()
    shortname = actor.id_.split("/")[-1]
    participant_id = f"{_case.id_}/participants/{shortname}"
    if participant_statuses:
        return as_CaseParticipant(
            id_=participant_id,
            name=actor.name,
            attributed_to=actor.id_,
            context=_case.id_,
            case_roles=case_roles,
            participant_statuses=participant_statuses,
        )
    return as_CaseParticipant(
        id_=participant_id,
        name=actor.name,
        attributed_to=actor.id_,
        context=_case.id_,
        case_roles=case_roles,
    )


def vendor_participant() -> as_CaseParticipant:
    """The vendor's participant record, including its report-management status."""
    _vendor = vendor()
    _case = case()

    _pstatus = as_ParticipantStatus(
        context=_case.id_,
        attributed_to=_vendor.id_,
        rm=RmDimension(state=RM.RECEIVED),
        vf=VfDimension(state=CS_vf.Vf),
    )
    return _participant_for(_vendor, [CVDRole.VENDOR], [_pstatus])


def finder_participant() -> as_CaseParticipant:
    """The finder's participant record; the finder is also the reporter here."""
    return _participant_for(finder(), [CVDRole.FINDER, CVDRole.REPORTER])


def add_vendor_participant_to_case() -> as_Add:
    _vendor = vendor()
    _case = case()

    activity = add_participant_to_case_activity(
        vendor_participant(),
        actor=_vendor.id_,
        target=_case.id_,
        content="We're adding ourselves as a participant to this case.",
    )
    return activity


def add_finder_participant_to_case() -> as_Add:
    _vendor = vendor()
    _case = case()

    activity = add_participant_to_case_activity(
        finder_participant(),
        actor=_vendor.id_,
        target=_case.id_,
        content="We're adding the finder as a participant to this case.",
    )
    return activity


def add_coordinator_participant_to_case() -> as_Add:
    _vendor = vendor()
    _case = case()

    activity = add_participant_to_case_activity(
        coordinator_participant(),
        actor=_vendor.id_,
        target=_case.id_,
        content="We're adding the coordinator as a participant to this case.",
    )
    return activity


def rm_invite_to_case() -> as_Invite:
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _case = case()
    _activity = rm_invite_to_case_activity(
        _coordinator,
        id_=f"{_case.id_}/invitation/1",
        actor=_vendor.id_,
        target=_case.id_,
        to=_coordinator.id_,
        content=f"We're inviting you to participate in {_case.name}.",
    )
    return _activity


def accept_invite_to_case() -> as_Accept:
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _case = case()
    _invite = rm_invite_to_case()
    _activity = rm_accept_invite_to_case_activity(
        _invite,
        actor=_coordinator.id_,
        to=_vendor.id_,
        content=f"We're accepting your invitation to participate in {_case.name}.",
    )
    return _activity


def reject_invite_to_case() -> as_Reject:
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _case = case()
    _invite = rm_invite_to_case()
    _activity = rm_reject_invite_to_case_activity(
        _invite,
        actor=_coordinator.id_,
        to=_vendor.id_,
        content=f"Thanks for the invitation, but we're declining to participate in {_case.name}.",
    )
    return _activity


def create_participant():
    _vendor = vendor()
    _case = case()
    _coordinator = _COORDINATOR
    _coord_participant = as_CaseParticipant(
        id_=f"{_case.id_}/participants/{_coordinator.id_}",
        name=_coordinator.name,
        attributed_to=_coordinator.id_,
        context=_case.id_,
        case_roles=[CVDRole.COORDINATOR],
    )
    _activity = as_Create(
        actor=_vendor.id_,
        object_=_coord_participant,
        context=_case.id_,
        content=f"We're adding {_coordinator.name} to the case.",
    )
    return _activity


def case_participant() -> as_CaseParticipant:
    participant = as_CaseParticipant(
        id_="https://vultron.example/cases/1/participants/vendor",
        name="Vendor",
        attributed_to="https://vultron.example/organizations/vendor",
        context="https://vultron.example/cases/1",
        case_roles=[CVDRole.VENDOR],
        participant_statuses=[participant_status()],
    )
    return participant


def coordinator_participant() -> as_CaseParticipant:
    """The coordinator's participant record."""
    return _participant_for(_COORDINATOR, [CVDRole.COORDINATOR])


def invite_to_case():
    _case = case()
    _coordinator = _COORDINATOR
    _vendor = vendor()

    activity = rm_invite_to_case_activity(
        _coordinator,
        id_=f"{_case.id_}/invitation/1",
        actor=_vendor.id_,
        target=_case.id_,
        to=_coordinator.id_,
        content=f"We're inviting you to participate in case {_case.name}.",
    )
    return activity


def remove_participant_from_case():
    _vendor = vendor()
    _case = case()
    coord_p = coordinator_participant()
    activity = remove_participant_from_case_activity(
        coord_p,
        actor=_vendor.id_,
        # `target`, not `origin`: RemoveCaseParticipantFromCasePattern
        # discriminates on target_, and ActivityPattern has no origin_ field, so
        # an origin-only Remove matches no pattern and never dispatches (#3438).
        target=_case.id_,
        summary="Vendor is removing the coordinator from the case.",
    )
    return activity
