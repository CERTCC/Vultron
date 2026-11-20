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

from vultron.core.models._helpers import URN_UUID_PREFIX
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.dimensions import (
    RmDimension,
    VfDimension,
)
from vultron.core.models.embargo_register import EmbargoRegisterEntry
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.states.cs import CS_vf
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    add_participant_to_case_activity,
    announce_admitted_act_activity,
    reinstate_participant_activity,
    remove_participant_activity,
    rm_accept_full_case_invite_activity,
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
    rm_invite_to_full_case_activity,
    rm_reject_full_case_invite_activity,
    rm_reject_invite_to_case_activity,
    rm_tentative_reject_full_case_invite_activity,
    update_participant_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Announce,
    as_Invite,
    as_Reject,
    as_Remove,
    as_Update,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.examples._base import (
    _CASE_ACTOR,
    _COORDINATOR,
    EXAMPLE_TIMESTAMP,
    _example_stamp,
    case,
    case_actor,
    example_uuid,
    finder,
    gen_report,
    vendor,
    vulnerability_item,
)
from vultron.wire.as2.vocab.examples.embargo import embargo_event
from vultron.wire.as2.vocab.examples.status import (
    participant_status,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus


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
            **_example_stamp(),
        )
    return as_CaseParticipant(
        id_=participant_id,
        name=actor.name,
        attributed_to=actor.id_,
        context=_case.id_,
        case_roles=case_roles,
        **_example_stamp(),
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
        **_example_stamp(),
    )
    return _participant_for(_vendor, [CVDRole.VENDOR], [_pstatus])


def finder_participant() -> as_CaseParticipant:
    """The finder's participant record; having reported, it holds REPORTER."""
    return _participant_for(finder(), [CVDRole.REPORTER])


def rm_invite_to_case() -> as_Invite:
    """The stub ``Invite`` to the example case, with an embargo in force.

    Its preview is cut from the case by the invitation profile (CM-17-010,
    ADR-0217): the stub summary, the case name and times, the Case Owner,
    the current status, the CVE ID of the vul item, and the embargo in force
    whole as the register's one entry the invitee consents to (CM-17-002,
    CM-17-011).  The case's content and its report are marked ``Redacted``.
    """
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _case = case(
        stub_summary=(
            "A memory-corruption vulnerability in widget"
            " — details shared after acceptance."
        ),
        content="The full technical write-up, shared with participants.",
        vulnerability_reports=[gen_report().id_],
        vulnerability_items=[vulnerability_item()],
        embargo_register=[
            EmbargoRegisterEntry(
                embargo=embargo_event(),
                status=EmbargoRegisterStatus.ACTIVE,
            )
        ],
    )
    _activity = rm_invite_to_case_activity(
        _coordinator,
        id_=f"{_case.id_}/invitation/1",
        actor=_vendor.id_,
        case=_case,
        to=_coordinator.id_,
        content=f"We're inviting you to participate in {_case.name}.",
        at=EXAMPLE_TIMESTAMP,
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
        at=EXAMPLE_TIMESTAMP,
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
        at=EXAMPLE_TIMESTAMP,
    )
    return _activity


def _coordinator_participant() -> as_CaseParticipant:
    _case = case()
    _coordinator = _COORDINATOR
    return as_CaseParticipant(
        id_=f"{_case.id_}/participants/{_coordinator.id_}",
        name=_coordinator.name,
        attributed_to=_coordinator.id_,
        context=_case.id_,
        case_roles=[CVDRole.COORDINATOR],
        **_example_stamp(),
    )


def add_participant_to_case() -> as_Add:
    """The CASE_MANAGER's ``Add(CaseParticipant, target=<case>)``.

    The CASE_MANAGER adds a participant record to the case when it sends a
    stub Invite and commits ``Add(CaseParticipant)`` as its own
    ``add_case_participant_to_case`` entry (ADR-0114).  No received use case
    handles it (ADR-0140 item 5), so the example is authored by the case
    actor and carries no sender-voice ``content``.
    """
    _case = case()
    return add_participant_to_case_activity(
        _coordinator_participant(),
        target=_case.id_,
        actor=case_actor().id_,
        context=_case.id_,
        at=EXAMPLE_TIMESTAMP,
    )


def update_participant() -> as_Update:
    """The CASE_MANAGER's ``Update(CaseParticipant)`` of a participant record.

    On an ownership transfer the CASE_MANAGER moves the ``CASE_OWNER`` role
    and commits each changed record in full as its own
    ``update_case_participant`` entry (CM-21-002, CLP-07-013).  No received
    use case handles it (ADR-0140 item 5).
    """
    _case = case()
    participant = _coordinator_participant()
    participant.case_roles = [CVDRole.COORDINATOR, CVDRole.CASE_OWNER]
    return update_participant_activity(
        participant,
        actor=case_actor().id_,
        context=_case.id_,
        at=EXAMPLE_TIMESTAMP,
    )


def case_participant() -> as_CaseParticipant:
    participant = as_CaseParticipant(
        id_="https://vultron.example/cases/1/participants/vendor",
        name="Vendor",
        attributed_to="https://vultron.example/organizations/vendor",
        context="https://vultron.example/cases/1",
        case_roles=[CVDRole.VENDOR],
        participant_statuses=[participant_status()],
        **_example_stamp(),
    )
    return participant


def coordinator_participant() -> as_CaseParticipant:
    """The coordinator's participant record."""
    return _participant_for(_COORDINATOR, [CVDRole.COORDINATOR])


def invite_to_case() -> as_Invite:
    """The RM ``Invite``, under the name the docs page and the generator use.

    One body, not two: this held a near-copy of :func:`rm_invite_to_case`,
    differing only in its ``content`` string (CS-22-001), and the generator
    wrote both functions to ``invite_to_case.json``, so whichever ran first
    was generated and overwritten on every run (#5776).  The surviving
    wording is ``rm_invite_to_case``'s, which drops the redundant "in case
    ... Case #" of the copy.
    """
    return rm_invite_to_case()


#: The Owner's acts carry fixed ids, so each ``Announce`` example embeds the
#: very act its own example shows (ADR-0199).
_REMOVAL_ID = f"{URN_UUID_PREFIX}{example_uuid('participant-removal')}"
_REINSTATEMENT_ID = (
    f"{URN_UUID_PREFIX}{example_uuid('participant-reinstatement')}"
)


def remove_participant_from_case() -> as_Remove:
    """The Case Owner (the vendor) removes the coordinator (CM-31-004).

    The Owner's own act, ``Remove(<Actor>, origin=<case>)``, sent to the
    CASE_MANAGER only and naming the coordinator as a typed reference
    (ADR-0199).
    """
    _case = case()
    return remove_participant_activity(
        _COORDINATOR.id_,
        _case.id_,
        actor=vendor().id_,
        to=[case_actor().id_],
        id_=_REMOVAL_ID,
        summary="Vendor is removing the coordinator from the case.",
        at=EXAMPLE_TIMESTAMP,
    )


def reinstate_participant_in_case() -> as_Add:
    """The Case Owner (the vendor) reinstates the removed coordinator (CM-31-011).

    The Owner's own act, ``Add(<Actor>, target=<case>)``, sent to the
    CASE_MANAGER only and naming the coordinator as a typed reference
    (ADR-0199).
    """
    _case = case()
    return reinstate_participant_activity(
        _COORDINATOR.id_,
        _case.id_,
        actor=vendor().id_,
        to=[case_actor().id_],
        id_=_REINSTATEMENT_ID,
        content="We're reinstating the coordinator in this case.",
        at=EXAMPLE_TIMESTAMP,
    )


def announce_participant_removal() -> as_Announce:
    """The CASE_MANAGER announces the Owner's admitted removal (ADR-0199).

    ``Announce(<the Owner's Remove>)`` to the removed coordinator: the act
    travels inline, keeping its own author and id, and ``inReplyTo`` names
    it.  It informs and asks nothing; the coordinator's replica takes the
    removal from the ledger entry.
    """
    removal = remove_participant_from_case()
    return announce_admitted_act_activity(
        removal,
        case().id_,
        actor=case_actor().id_,
        to=[_COORDINATOR.id_],
        id_=derived_activity_id("announce-admitted-act", removal.id_),
        at=EXAMPLE_TIMESTAMP,
    )


def announce_participant_reinstatement() -> as_Announce:
    """The CASE_MANAGER announces the Owner's admitted reinstatement (ADR-0199)."""
    reinstatement = reinstate_participant_in_case()
    return announce_admitted_act_activity(
        reinstatement,
        case().id_,
        actor=case_actor().id_,
        to=[_COORDINATOR.id_],
        id_=derived_activity_id("announce-admitted-act", reinstatement.id_),
        at=EXAMPLE_TIMESTAMP,
    )


#: The ledger position in the full-case Invite examples.  The participant has
#: replayed the whole ledger, so its tail when it answers equals the
#: CASE_MANAGER's tail when it asked.
_LEDGER_TAIL = LedgerPosition(log_index=4, entry_hash="b2c3d4e5" * 8)


def invite_to_full_case() -> as_Invite:
    """The full-case Invite: the CASE_MANAGER asks a joined participant to judge the case."""
    _case = case()
    _coordinator = _COORDINATOR
    return rm_invite_to_full_case_activity(
        _coordinator,
        _case,
        _LEDGER_TAIL,
        id_=f"{_case.id_}/full-case-invitation/1",
        actor=_CASE_ACTOR.id_,
        to=_coordinator.id_,
        at=EXAMPLE_TIMESTAMP,
    )


def accept_full_case_invite() -> as_Accept:
    """The participant judges the case valid (RM ``VALID``)."""
    return rm_accept_full_case_invite_activity(
        invite_to_full_case(),
        _LEDGER_TAIL,
        actor=_COORDINATOR.id_,
        to=_CASE_ACTOR.id_,
        at=EXAMPLE_TIMESTAMP,
    )


def tentative_reject_full_case_invite() -> as_Reject:
    """The participant judges the case invalid (RM ``INVALID``)."""
    return rm_tentative_reject_full_case_invite_activity(
        invite_to_full_case(),
        _LEDGER_TAIL,
        actor=_COORDINATOR.id_,
        to=_CASE_ACTOR.id_,
        at=EXAMPLE_TIMESTAMP,
    )


def reject_full_case_invite() -> as_Reject:
    """The participant closes the case (RM ``CLOSED``)."""
    return rm_reject_full_case_invite_activity(
        invite_to_full_case(),
        _LEDGER_TAIL,
        actor=_COORDINATOR.id_,
        to=_CASE_ACTOR.id_,
        at=EXAMPLE_TIMESTAMP,
    )
