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
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
)
from vultron.core.states.rm import RM

CASE_ID = "https://example.org/cases/active-predicate"
ACTOR_ID = "https://example.org/actors/participant"
EMBARGO_ID = f"{CASE_ID}/embargoes/e1"
REVISION_ID = f"{CASE_ID}/embargoes/e2"
S = EmbargoConsentState


def _case(*, embargo: bool) -> VulnerabilityCase:
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=ACTOR_ID)
    if embargo:
        case.set_embargo(EMBARGO_ID)
    return case


def _participant(
    *,
    joined: bool = True,
    consents: dict[str, EmbargoConsentState] | None = None,
    rm_state: RM = RM.ACCEPTED,
) -> CaseParticipant:
    return CaseParticipant(
        attributed_to=ACTOR_ID,
        context=CASE_ID,
        joined=joined,
        embargo_consents=[
            EmbargoConsent(embargo_id=eid, state=state)
            for eid, state in (consents or {}).items()
        ],
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
@pytest.mark.parametrize(
    "consents",
    [
        {},
        {EMBARGO_ID: S.INVITED},
        {EMBARGO_ID: S.DECLINED},
        {EMBARGO_ID: S.EXPIRED},
        {EMBARGO_ID: S.ACCEPTED},
    ],
    ids=["never-asked", "invited", "declined", "expired", "accepted"],
)
def test_joined_participant_is_active_with_no_embargo(
    consents: dict[str, EmbargoConsentState],
) -> None:
    """With no active embargo, any participant that joined is active.

    The consent rows are not consulted: there is nothing to be bound by.
    """
    case = _case(embargo=False)
    assert not case.embargo_in_force
    assert case.is_active_participant(_participant(consents=consents))


@pytest.mark.spec("CM-10-004")
@pytest.mark.parametrize(
    ("consents", "active"),
    [
        ({EMBARGO_ID: S.ACCEPTED}, True),
        ({EMBARGO_ID: S.ACCEPTED, REVISION_ID: S.INVITED}, True),
        ({}, False),
        ({EMBARGO_ID: S.INVITED}, False),
        ({EMBARGO_ID: S.EXPIRED}, False),
        ({EMBARGO_ID: S.DECLINED}, False),
        ({REVISION_ID: S.ACCEPTED}, False),
    ],
    ids=[
        "signatory",
        "signatory-asked-about-revision",
        "never-asked",
        "invited",
        "expired",
        "declined",
        "accepted-another-embargo-only",
    ],
)
def test_active_embargo_requires_signatory(
    consents: dict[str, EmbargoConsentState], active: bool
) -> None:
    """While an embargo is active, only a signatory of it is active."""
    case = _case(embargo=True)
    assert case.embargo_in_force
    assert (
        case.is_active_participant(_participant(consents=consents)) is active
    )


@pytest.mark.spec("CM-10-004", "CM-18-001")
def test_longer_revision_excludes_a_non_accepting_signatory() -> None:
    """A participant that signed A lapses from the gate when a longer B activates.

    Nothing is written to its rows at activation; the gate reads
    ``is_signatory(active_embargo_id)`` and the lapse is derived.
    """
    case = _case(embargo=True)
    participant = _participant(consents={EMBARGO_ID: S.ACCEPTED})
    assert case.is_active_participant(participant)

    case.set_embargo(REVISION_ID)

    assert participant.has_lapsed(case.active_embargo_id)
    assert not case.is_active_participant(participant)
    assert participant.consent_for(EMBARGO_ID) is S.ACCEPTED

    participant.apply_pec_transition(REVISION_ID, PEC_Trigger.ACCEPT)
    assert case.is_active_participant(participant)
    assert not participant.has_lapsed(case.active_embargo_id)


@pytest.mark.spec("CM-10-004")
@pytest.mark.parametrize("embargo", [False, True])
def test_unjoined_participant_is_inert(embargo: bool) -> None:
    """A participant that has not accepted its stub Invite is never active."""
    case = _case(embargo=embargo)
    participant = _participant(joined=False, consents={EMBARGO_ID: S.ACCEPTED})
    assert not case.is_active_participant(participant)


@pytest.mark.parametrize("embargo", [False, True])
def test_closed_participant_stays_active(embargo: bool) -> None:
    """RM.CLOSED is not part of the active check (CM-23-002, #4100).

    A closed participant's replica still learns how the case ended, so the
    shared selection drops it only where CM-23-004 is named.
    """
    case = _case(embargo=embargo)
    participant = _participant(
        rm_state=RM.CLOSED, consents={EMBARGO_ID: S.ACCEPTED}
    )
    assert participant.rm_closed
    assert case.is_active_participant(participant)


def test_no_statuses_is_not_closed() -> None:
    participant = CaseParticipant(attributed_to=ACTOR_ID, context=CASE_ID)
    assert not participant.rm_closed
