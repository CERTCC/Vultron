#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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

"""Seat an ownership-transfer transferee on a case in a given standing.

An ownership-transfer Offer carries the case inline, so the CASE_MANAGER
offers it only to an active participant whose closure is not recorded, and
admits the transferee's Accept only while it still is (CM-21-021,
CM-10-004).  Tests that offer a case seat the transferee with
:func:`seat_transferee`; tests of the refusal seat it in each
:data:`INACTIVE_STANDINGS` (CS-22-001).
"""

from enum import Enum

from test.support.embargo_register import activate
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.participant_embargo_consent import EmbargoConsentState
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole


class TransfereeStanding(Enum):
    """Where a transferee stands on the case it is offered."""

    ACTIVE = "active"
    """Joined, not removed, not closed; no embargo is in force."""

    OFF_ROSTER = "off the roster"
    """The case holds no participant record for it."""

    INVITEE = "an invitee that has not accepted"
    """Its stub Invite is unanswered (``joined`` false)."""

    REMOVED = "removed"
    """It carries the removal fact (CM-31-001)."""

    NON_SIGNATORY = "not a signatory to the active embargo"
    """An embargo is in force and its consent row for it is not ``AGREED``."""

    CLOSED = "closed"
    """Its closure is recorded (RM ``CLOSED``)."""


#: Every standing the CASE_MANAGER refuses a transferee in (CM-21-021).
INACTIVE_STANDINGS = tuple(
    s for s in TransfereeStanding if s is not TransfereeStanding.ACTIVE
)


def transferee_participant_id(actor_id: str) -> str:
    """The participant record id :func:`seat_transferee` gives *actor_id*."""
    return f"{actor_id}/transferee-participant"


def _activate_embargo_without(
    case: VulnerabilityCase, dl: CasePersistence, actor_id: str
) -> None:
    """Put an embargo in force that every listed participant but *actor_id*
    agreed to; *actor_id*'s row for it is ``INVITED``."""
    embargo = EmbargoEvent(
        id_=f"{case.id_}/transferee-test-embargo",
        context=case.id_,
        end_time=days_from_now_utc(45),
    )
    dl.save(embargo)
    activate(case, embargo)
    for listed_id, participant_id in case.actor_participant_index.items():
        record = dl.read(participant_id)
        if not isinstance(record, CaseParticipant):
            continue
        state = (
            EmbargoConsentState.INVITED
            if listed_id == actor_id
            else EmbargoConsentState.AGREED
        )
        record.embargo_consents = [
            row
            for row in record.embargo_consents
            if row.embargo_id != embargo.id_
        ] + [EmbargoConsent(embargo_id=embargo.id_, state=state)]
        dl.save(record)


def make_inactive(
    case: VulnerabilityCase,
    dl: CasePersistence,
    actor_id: str,
    standing: TransfereeStanding,
) -> None:
    """Move the already-seated, active *actor_id* into *standing*.

    For a transferee that was active when the case was offered to it and
    lapsed before it accepted (CM-21-021).  Saves the case and the record.
    """
    record = dl.read(case.actor_participant_index[actor_id])
    assert isinstance(record, CaseParticipant)
    if standing is TransfereeStanding.OFF_ROSTER:
        del case.actor_participant_index[actor_id]
        case.case_participants = [
            p
            for p in case.case_participants
            if (p if isinstance(p, str) else p.id_) != record.id_
        ]
    elif standing is TransfereeStanding.INVITEE:
        record.joined = False
    elif standing is TransfereeStanding.REMOVED:
        record.record_removal(f"{case.id_}/transferee-test-removal")
    elif standing is TransfereeStanding.CLOSED:
        record.participant_statuses.append(
            ParticipantStatus(
                context=case.id_,
                attributed_to=actor_id,
                rm=RmDimension(state=RM.CLOSED),
            )
        )
    elif standing is TransfereeStanding.NON_SIGNATORY:
        _activate_embargo_without(case, dl, actor_id)
        dl.save(case)
        return
    dl.save(record)
    dl.save(case)


def transferee_record(
    case: VulnerabilityCase,
    actor_id: str,
    roles: list[CVDRole] | None = None,
) -> CaseParticipant:
    """An active participant record for *actor_id*, added to *case*.

    Neither is saved: the caller persists the record and the case.
    """
    record = CaseParticipant(
        id_=transferee_participant_id(actor_id),
        attributed_to=actor_id,
        context=case.id_,
        case_roles=list(roles or [CVDRole.COORDINATOR]),
    )
    case.add_participant(record)
    return record


def seat_transferee(
    case: VulnerabilityCase,
    dl: CasePersistence,
    actor_id: str,
    standing: TransfereeStanding = TransfereeStanding.ACTIVE,
    roles: list[CVDRole] | None = None,
) -> None:
    """Give *case* a participant record for *actor_id* in *standing*.

    Saves the record and the case.  :attr:`TransfereeStanding.OFF_ROSTER`
    seats nothing.
    """
    if standing is not TransfereeStanding.OFF_ROSTER:
        dl.save(transferee_record(case, actor_id, roles))
    dl.save(case)
    if standing not in (
        TransfereeStanding.ACTIVE,
        TransfereeStanding.OFF_ROSTER,
    ):
        make_inactive(case, dl, actor_id, standing)
