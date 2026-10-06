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

"""The shared recipient selection (CM-10-004, CM-10-007, #4046 AC-2/AC-3)."""

import logging

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.participants.recipients import (
    case_content_participants,
    case_content_recipients,
    inert_participants,
    invitation_recipients,
    is_case_content_recipient,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM

_CASE_ID = "https://example.org/cases/recipients-001"
_SENDER = "https://example.org/actors/sender"
_SIGNATORY = "https://example.org/actors/signatory"
_INVITED = "https://example.org/actors/invited"
_UNJOINED = "https://example.org/actors/unjoined"
_CLOSED = "https://example.org/actors/closed"
_EMBARGO_ID = f"{_CASE_ID}/embargoes/e1"


@pytest.fixture()
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_SENDER)


def _seat(
    dl: SqliteDataLayer,
    case: VulnerabilityCase,
    actor_id: str,
    *,
    consent: EmbargoConsentState | None = EmbargoConsentState.ACCEPTED,
    joined: bool = True,
    rm_state: RM = RM.ACCEPTED,
    store: bool = True,
) -> CaseParticipant:
    participant = CaseParticipant(
        id_=f"{_CASE_ID}/participants/{actor_id.rsplit('/', 1)[-1]}",
        attributed_to=actor_id,
        context=_CASE_ID,
        joined=joined,
        embargo_consents=(
            [EmbargoConsent(embargo_id=_EMBARGO_ID, state=consent)]
            if consent is not None
            else []
        ),
        participant_statuses=[
            ParticipantStatus(
                context=_CASE_ID,
                attributed_to=actor_id,
                rm=RmDimension(state=rm_state),
            )
        ],
    )
    if store:
        dl.create(participant)
    case.case_participants.append(participant.id_)
    case.actor_participant_index[actor_id] = participant.id_
    return participant


def _embargoed_case(dl: SqliteDataLayer) -> VulnerabilityCase:
    """A case under an active embargo with one participant of each kind."""
    case = VulnerabilityCase(id_=_CASE_ID, attributed_to=_SENDER)
    case.set_embargo(_EMBARGO_ID)
    _seat(dl, case, _SENDER)
    _seat(dl, case, _SIGNATORY)
    _seat(dl, case, _INVITED, consent=EmbargoConsentState.INVITED)
    _seat(
        dl, case, _UNJOINED, consent=EmbargoConsentState.INVITED, joined=False
    )
    _seat(dl, case, _CLOSED, rm_state=RM.CLOSED)
    return case


@pytest.mark.spec("CM-10-004")
def test_case_content_reaches_only_active_participants(
    dl: SqliteDataLayer,
) -> None:
    case = _embargoed_case(dl)
    assert case_content_recipients(case, dl, excluding={_SENDER}) == [
        _SIGNATORY,
        _CLOSED,
    ]


@pytest.mark.spec("CM-23-004")
def test_skip_closed_also_leaves_out_closed_participants(
    dl: SqliteDataLayer,
) -> None:
    case = _embargoed_case(dl)
    assert case_content_recipients(
        case, dl, excluding={_SENDER}, skip_closed=True
    ) == [_SIGNATORY]


@pytest.mark.spec("CM-10-004")
def test_with_no_embargo_every_joined_open_participant_is_active(
    dl: SqliteDataLayer,
) -> None:
    case = VulnerabilityCase(id_=_CASE_ID, attributed_to=_SENDER)
    _seat(dl, case, _SIGNATORY, consent=None)
    _seat(dl, case, _INVITED, consent=EmbargoConsentState.DECLINED)
    _seat(dl, case, _UNJOINED, joined=False)
    _seat(dl, case, _CLOSED, rm_state=RM.CLOSED)
    assert case_content_recipients(case, dl) == [_SIGNATORY, _INVITED, _CLOSED]


@pytest.mark.spec("CM-10-007")
def test_invitations_reach_inert_participants_but_not_closed_ones(
    dl: SqliteDataLayer,
) -> None:
    case = _embargoed_case(dl)
    assert invitation_recipients(case, dl, excluding={_SENDER}) == [
        _SIGNATORY,
        _INVITED,
        _UNJOINED,
    ]


def test_inert_participants_is_the_roster_minus_the_active(
    dl: SqliteDataLayer,
) -> None:
    case = _embargoed_case(dl)
    assert inert_participants(case, dl) == {_INVITED, _UNJOINED}


@pytest.mark.spec("CM-10-004")
def test_single_recipient_check(dl: SqliteDataLayer) -> None:
    case = _embargoed_case(dl)
    assert is_case_content_recipient(case, dl, _SIGNATORY)
    assert not is_case_content_recipient(case, dl, _INVITED)
    assert not is_case_content_recipient(case, dl, _UNJOINED)
    assert not is_case_content_recipient(
        case, dl, "https://example.org/actors/stranger"
    )


@pytest.mark.spec("CM-10-004")
def test_unresolvable_record_is_withheld_with_a_warning(
    dl: SqliteDataLayer, caplog: pytest.LogCaptureFixture
) -> None:
    """Fail closed: a roster entry the case cannot vouch for gets nothing."""
    case = VulnerabilityCase(id_=_CASE_ID, attributed_to=_SENDER)
    _seat(dl, case, _SIGNATORY)
    _seat(dl, case, _INVITED, store=False)
    with caplog.at_level(logging.WARNING):
        assert case_content_recipients(case, dl) == [_SIGNATORY]
        assert invitation_recipients(case, dl) == [_SIGNATORY]
        assert not is_case_content_recipient(case, dl, _INVITED)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(_INVITED in r.getMessage() for r in warnings)


def test_stored_record_wins_over_a_stale_inline_copy(
    dl: SqliteDataLayer,
) -> None:
    """The stored record is consulted first, as ``iter_case_participants`` does.

    Participant writes save the stored record, so an inline copy the case
    carries can be stale.
    """
    case = VulnerabilityCase(id_=_CASE_ID, attributed_to=_SENDER)
    stored = _seat(dl, case, _SIGNATORY, joined=False)
    case.case_participants[0] = stored.model_copy(update={"joined": True})
    assert case_content_recipients(case, dl) == []


def test_inline_copy_is_the_fallback_when_nothing_is_stored(
    dl: SqliteDataLayer,
) -> None:
    """During bootstrap the inline copy is all there is, and it is used."""
    case = VulnerabilityCase(id_=_CASE_ID, attributed_to=_SENDER)
    case.case_participants[0] = _seat(dl, case, _SIGNATORY, store=False)
    assert case_content_recipients(case, dl) == [_SIGNATORY]


def test_case_content_participants_pairs_each_recipient_with_its_record(
    dl: SqliteDataLayer,
) -> None:
    """The pairs carry the record the selection resolved, inline-only included.

    A caller that narrows by a record field (the bootstrap reporter filter)
    must not read the record again: an inline-only record would vanish.
    """
    case = VulnerabilityCase(id_=_CASE_ID, attributed_to=_SENDER)
    stored = _seat(dl, case, _SIGNATORY)
    inline = _seat(dl, case, _INVITED, store=False)
    case.case_participants[1] = inline
    _seat(dl, case, _UNJOINED, joined=False)
    pairs = case_content_participants(case, dl)
    assert [(a, p.id_) for a, p in pairs] == [
        (_SIGNATORY, stored.id_),
        (_INVITED, inline.id_),
    ]
    assert [a for a, _ in pairs] == case_content_recipients(case, dl)
