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

"""Unit tests for ``CreateInertInviteeParticipantNode`` (CM-11-006, BTND-05-003).

The node seats the stub-Invite invitee as an inert participant and builds and
attaches the record through the shared ``_create_and_attach_participant``
helper (BTND-05-003).  These tests pin the seating result and the idempotency
on an existing record, so the routing through the helper preserves behaviour.
"""

from typing import Any, cast
from unittest.mock import patch

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.embargo_register import activate
from vultron.core.behaviors.case.nodes import invite_inert_participant
from vultron.core.behaviors.case.nodes.invite_inert_participant import (
    CreateInertInviteeParticipantNode,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_vf
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

MANAGER_ID = "https://example.org/actors/vendor"
INVITEE_ID = "https://example.org/actors/invitee"
CASE_ID = "https://example.org/cases/case-001"
PARTICIPANT_ID = f"{CASE_ID}/participants/invitee"


@pytest.fixture
def scenario() -> BTTestScenario:
    s = BTTestScenario(actor_id=MANAGER_ID)
    s.seed(
        CaseActor(id_=MANAGER_ID, name="Vendor Co"),
        VulnerabilityCase(id_=CASE_ID, name="Test Case"),
    )
    return s


def _run(scenario: BTTestScenario, roles: list[str] | None) -> Any:
    return scenario.run(
        CreateInertInviteeParticipantNode(
            invitee_id=INVITEE_ID, case_id=CASE_ID, roles=roles
        ),
        case_id=CASE_ID,
    )


def _case(scenario: BTTestScenario) -> VulnerabilityCase:
    return cast(VulnerabilityCase, scenario.dl.read_case(CASE_ID))


def _participant(scenario: BTTestScenario) -> CaseParticipant:
    return cast(CaseParticipant, scenario.dl.read(PARTICIPANT_ID))


def _seed_existing(scenario: BTTestScenario, *, joined: bool) -> None:
    """Seat a pre-existing record for the invitee at RM ``ACCEPTED``."""
    existing = CaseParticipant(
        id_=PARTICIPANT_ID,
        attributed_to=INVITEE_ID,
        context=CASE_ID,
        case_roles=[CVDRole.FINDER],
        participant_statuses=[
            ParticipantStatus(
                context=CASE_ID,
                attributed_to=INVITEE_ID,
                rm=RmDimension(state=RM.ACCEPTED),
                cvd_role=[CVDRole.FINDER],
            )
        ],
        joined=joined,
    )
    scenario.dl.create(existing)
    case = _case(scenario)
    case.add_participant(existing)
    scenario.dl.save(case)


class TestSeating:
    @pytest.mark.spec("CM-11-006")
    def test_seats_inert_vendor_invitee_at_rm_received(
        self, scenario: BTTestScenario
    ) -> None:
        scenario.assert_success(_run(scenario, ["VENDOR"]))

        case = _case(scenario)
        assert case.actor_participant_index[INVITEE_ID] == PARTICIPANT_ID
        participant = _participant(scenario)
        assert participant.joined is False
        assert participant.case_roles == [CVDRole.VENDOR]
        assert len(participant.participant_statuses) == 1
        status = participant.participant_statuses[0]
        assert status.rm.state == RM.RECEIVED
        assert status.vf is not None
        assert status.vf.state == CS_vf.vf

    def test_non_vendor_invitee_has_no_vf_dimension(
        self, scenario: BTTestScenario
    ) -> None:
        scenario.assert_success(_run(scenario, ["FINDER"]))

        status = _participant(scenario).participant_statuses[0]
        assert status.vf is None

    @pytest.mark.spec("CM-11-006")
    def test_active_embargo_gives_invited_consent_row(
        self, scenario: BTTestScenario
    ) -> None:
        embargo = EmbargoEvent(context=CASE_ID, end_time=days_from_now_utc(45))
        scenario.dl.create(embargo)
        case = _case(scenario)
        activate(case, embargo.id_)
        scenario.dl.save(case)

        scenario.assert_success(_run(scenario, ["VENDOR"]))

        participant = _participant(scenario)
        assert (
            participant.consent_for(embargo.id_) == EmbargoConsentState.INVITED
        )
        assert not participant.is_signatory(embargo.id_)

    def test_no_embargo_gives_no_consent_row(
        self, scenario: BTTestScenario
    ) -> None:
        scenario.assert_success(_run(scenario, ["VENDOR"]))

        assert _participant(scenario).embargo_consents == []

    @pytest.mark.spec("BTND-05-003")
    def test_create_and_attach_goes_through_shared_helper(
        self, scenario: BTTestScenario
    ) -> None:
        real = invite_inert_participant._create_and_attach_participant
        with patch.object(
            invite_inert_participant,
            "_create_and_attach_participant",
            side_effect=real,
        ) as spy:
            scenario.assert_success(_run(scenario, ["VENDOR"]))

        spy.assert_called_once()
        assert spy.call_args.kwargs["case_id"] == CASE_ID
        assert spy.call_args.kwargs["actor_id_for_index"] == INVITEE_ID


class TestRefusals:
    @pytest.mark.spec("CM-11-019")
    def test_no_roles_fails_and_writes_nothing(
        self, scenario: BTTestScenario
    ) -> None:
        result = _run(scenario, None)

        assert result.status == Status.FAILURE
        assert "CM-11-019" in (result.feedback_message or "")
        scenario.assert_object_absent(PARTICIPANT_ID)
        assert INVITEE_ID not in _case(scenario).actor_participant_index

    def test_missing_case_fails(self) -> None:
        scenario = BTTestScenario(actor_id=MANAGER_ID)
        scenario.seed(CaseActor(id_=MANAGER_ID, name="Vendor Co"))

        result = _run(scenario, ["VENDOR"])

        assert result.status == Status.FAILURE
        scenario.assert_object_absent(PARTICIPANT_ID)


class TestIdempotency:
    def test_joined_participant_is_left_unchanged(
        self, scenario: BTTestScenario
    ) -> None:
        """A joined participant is never re-seated, even with no roles."""
        _seed_existing(scenario, joined=True)

        scenario.assert_success(_run(scenario, None))

        participant = _participant(scenario)
        assert participant.joined is True
        assert participant.case_roles == [CVDRole.FINDER]
        assert participant.participant_statuses[-1].rm.state == RM.ACCEPTED

    def test_existing_inert_record_wins(
        self, scenario: BTTestScenario
    ) -> None:
        """An existing inert record is kept, not reset (case-joining re-invite).

        The helper's "existing record wins" rule: the node seats nothing new
        and does not raise on the duplicate id.
        """
        _seed_existing(scenario, joined=False)

        scenario.assert_success(_run(scenario, ["VENDOR"]))

        participant = _participant(scenario)
        assert participant.joined is False
        assert participant.case_roles == [CVDRole.FINDER]
        assert len(participant.participant_statuses) == 1
        assert participant.participant_statuses[0].rm.state == RM.ACCEPTED
        case = _case(scenario)
        assert case.actor_participant_index[INVITEE_ID] == PARTICIPANT_ID
