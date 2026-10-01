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
"""The one active-participant predicate (CM-10-004, ADR-0114, #4046 AC-1)."""

import pytest

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM

CASE_ID = "https://example.org/cases/active-predicate"
ACTOR_ID = "https://example.org/actors/participant"
EMBARGO_ID = f"{CASE_ID}/embargoes/e1"


def _case(*, embargo: bool) -> VulnerabilityCase:
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=ACTOR_ID)
    if embargo:
        case.set_embargo(EMBARGO_ID)
    return case


def _participant(
    *,
    joined: bool = True,
    consent: PEC = PEC.UNBOUND,
    rm_state: RM = RM.ACCEPTED,
) -> CaseParticipant:
    return CaseParticipant(
        attributed_to=ACTOR_ID,
        context=CASE_ID,
        joined=joined,
        embargo_consent_state=consent,
        participant_statuses=[
            ParticipantStatus(
                context=CASE_ID,
                attributed_to=ACTOR_ID,
                rm=RmDimension(state=rm_state),
            )
        ],
    )


def test_joined_defaults_true_and_round_trips() -> None:
    """Every record today is seated or accepted, so ``joined`` defaults True."""
    assert CaseParticipant(attributed_to=ACTOR_ID, context=CASE_ID).joined
    inert = _participant(joined=False)
    restored = CaseParticipant.model_validate(inert.model_dump(by_alias=True))
    assert restored.joined is False


@pytest.mark.spec("CM-10-004")
def test_joined_participant_is_active_with_no_embargo() -> None:
    """With no active embargo, a participant that joined is active."""
    case = _case(embargo=False)
    for consent in (PEC.UNBOUND, PEC.DECLINED, PEC.LAPSED):
        assert case.is_active_participant(_participant(consent=consent))


@pytest.mark.spec("CM-10-004")
@pytest.mark.parametrize(
    ("consent", "active"),
    [
        (PEC.SIGNATORY, True),
        (PEC.INVITED, False),
        (PEC.UNBOUND, False),
        (PEC.LAPSED, False),
        (PEC.DECLINED, False),
    ],
)
def test_active_embargo_requires_signatory(consent: PEC, active: bool) -> None:
    """While an embargo is active, only a SIGNATORY is active."""
    case = _case(embargo=True)
    assert case.embargo_in_force
    assert case.is_active_participant(_participant(consent=consent)) is active


@pytest.mark.spec("CM-10-004")
@pytest.mark.parametrize("embargo", [False, True])
def test_unjoined_participant_is_inert(embargo: bool) -> None:
    """A participant that has not accepted its stub Invite is never active."""
    case = _case(embargo=embargo)
    participant = _participant(joined=False, consent=PEC.SIGNATORY)
    assert not case.participant_holds_seat(participant)
    assert not case.is_active_participant(participant)


@pytest.mark.parametrize("embargo", [False, True])
def test_closed_participant_holds_no_seat_but_stays_active(
    embargo: bool,
) -> None:
    """RM.CLOSED is not part of the active check (CM-23-002).

    A closed participant has left, so it holds no seat and the consent
    cascades leave it alone; but its replica still learns how the case ended,
    so the shared selection drops it only where CM-23-004 is named.
    """
    case = _case(embargo=embargo)
    participant = _participant(rm_state=RM.CLOSED, consent=PEC.SIGNATORY)
    assert participant.rm_closed
    assert not case.participant_holds_seat(participant)
    assert case.is_active_participant(participant)


def test_no_statuses_is_not_closed() -> None:
    participant = CaseParticipant(attributed_to=ACTOR_ID, context=CASE_ID)
    assert not participant.rm_closed
