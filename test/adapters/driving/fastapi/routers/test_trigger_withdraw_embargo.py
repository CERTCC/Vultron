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

"""
Tests for the withdraw-embargo trigger endpoint
(POST /actors/{actor_id}/trigger/withdraw-embargo, EP-09-013).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status

from test.support.embargo_register import activate
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from .conftest import _add_case_manager

_OWNER = "https://example.org/actors/vendor"


@pytest.fixture(autouse=True)
def _no_outbox_delivery():
    """Suppress real outbox delivery for every test in this module."""
    with patch(
        "vultron.adapters.driving.fastapi.trigger_runner.outbox_handler",
        new_callable=AsyncMock,
    ):
        yield


def _case_with_signatory(
    dl, actor_id: str, consent: EmbargoConsentState
) -> tuple[VulnerabilityCase, as_EmbargoEvent]:
    """A case another actor owns, with *actor_id* holding *consent*."""
    case = VulnerabilityCase(name="WITHDRAW-CASE", attributed_to=_OWNER)
    embargo = as_EmbargoEvent(context=case.id_, end_time=days_from_now_utc(45))
    dl.create(embargo)
    activate(case, embargo.id_)
    dl.create(case)
    _add_case_manager(case, dl)
    participant = as_CaseParticipant(
        attributed_to=actor_id,
        context=case.id_,
        case_roles=[CVDRole.FINDER],
    )
    case.add_participant(participant)
    participant.embargo_consents = [
        EmbargoConsent(embargo_id=embargo.id_, state=consent)
    ]
    dl.create(participant)
    dl.save(case)
    return case, embargo


def test_trigger_withdraw_embargo_returns_202_with_the_leave(
    client_triggers, actor, dl
):
    """TB-01-002, TB-04-001: a signatory's Leave(EmbargoEvent) is returned."""
    case, embargo = _case_with_signatory(
        dl, actor.id_, EmbargoConsentState.AGREED
    )

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/withdraw-embargo",
        json={"case_id": case.id_},
    )

    assert resp.status_code == status.HTTP_202_ACCEPTED, resp.text
    activity = resp.json()["activity"]
    assert activity["type"] == "Leave"
    assert activity["object"]["id"] == embargo.id_


def test_trigger_withdraw_embargo_from_an_invited_row_returns_409(
    client_triggers, actor, dl
):
    """EP-09-013: a row that is not AGREED has nothing to withdraw from."""
    case, _ = _case_with_signatory(dl, actor.id_, EmbargoConsentState.INVITED)

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/withdraw-embargo",
        json={"case_id": case.id_},
    )

    assert resp.status_code == status.HTTP_409_CONFLICT


def test_trigger_withdraw_embargo_missing_case_id_returns_422(
    client_triggers, actor
):
    """TB-03-001: Request missing case_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/withdraw-embargo", json={}
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
