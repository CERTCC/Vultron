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

"""Tests for GetActionRulesUseCase (CA-2).

Verifies CM-07-001, CM-07-002, CM-07-003, AR-07-001, AR-07-002.
"""

import pytest

from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.core.states.roles import CVDRoles as CVDRole
from vultron.core.use_cases.action_rules import (
    ActionRulesRequest,
    GetActionRulesUseCase,
)
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    CaseStatus,
    ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

ACTOR_ID = "https://example.org/actors/alice"
CASE_ID = "https://example.org/cases/c1"
PARTICIPANT_ID = "https://example.org/participants/p1"


@pytest.fixture
def dl():
    """In-memory DataLayer with a minimal valid case setup."""
    layer = TinyDbDataLayer(db_path=None)

    # Case: VulnerabilityCase with actor_participant_index
    case = VulnerabilityCase(
        as_id=CASE_ID,
        name="Test Case",
        actor_participant_index={ACTOR_ID: PARTICIPANT_ID},
        case_statuses=[CaseStatus(em_state=EM.ACTIVE, pxa_state=CS_pxa.Pxa)],
    )
    layer.create(case)

    # Participant: CaseParticipant with VENDOR role and ACCEPTED RM state
    participant = CaseParticipant(
        as_id=PARTICIPANT_ID,
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.VENDOR],
        participant_statuses=[
            ParticipantStatus(
                context=CASE_ID, rm_state=RM.ACCEPTED, vfd_state=CS_vfd.VFd
            )
        ],
    )
    layer.create(participant)

    return layer


@pytest.fixture
def request_(dl):
    return ActionRulesRequest(
        case_id=CASE_ID,
        actor_id=ACTOR_ID,
    )


class TestGetActionRulesUseCase:
    """Tests for the GetActionRulesUseCase."""

    def test_happy_path_returns_expected_keys(self, dl, request_):
        """Happy path: result contains all required state and action keys."""
        result = GetActionRulesUseCase(dl=dl, request=request_).execute()

        expected_keys = {
            "participant_id",
            "participant_actor_id",
            "case_id",
            "role",
            "rm_state",
            "em_state",
            "vfd_state",
            "pxa_state",
            "cs_state",
            "actions",
        }
        assert expected_keys.issubset(result.keys())

    def test_happy_path_state_values(self, dl, request_):
        """States in the response match what was stored."""
        result = GetActionRulesUseCase(dl=dl, request=request_).execute()

        assert result["rm_state"] == RM.ACCEPTED
        assert result["em_state"] == EM.ACTIVE
        assert result["vfd_state"] == CS_vfd.VFd.name
        assert result["pxa_state"] == CS_pxa.Pxa.name
        assert result["cs_state"] == CS_vfd.VFd.name + CS_pxa.Pxa.name

    def test_happy_path_role(self, dl, request_):
        """Participant role is reflected in the response."""
        result = GetActionRulesUseCase(dl=dl, request=request_).execute()
        assert CVDRole.VENDOR.name in result["role"]

    def test_happy_path_ids(self, dl, request_):
        """IDs in the response match the stored object IDs."""
        result = GetActionRulesUseCase(dl=dl, request=request_).execute()
        assert result["participant_id"] == PARTICIPANT_ID
        assert result["participant_actor_id"] == ACTOR_ID
        assert result["case_id"] == CASE_ID

    def test_happy_path_actions_is_list(self, dl, request_):
        """actions key is a non-empty list of dicts with name and description."""
        result = GetActionRulesUseCase(dl=dl, request=request_).execute()
        assert isinstance(result["actions"], list)
        assert len(result["actions"]) > 0
        for action in result["actions"]:
            assert "name" in action
            assert "description" in action

    def test_case_not_found_raises(self, dl):
        """Missing case raises VultronNotFoundError."""
        req = ActionRulesRequest(
            case_id="https://example.org/cases/does-not-exist",
            actor_id=ACTOR_ID,
        )
        with pytest.raises(VultronNotFoundError):
            GetActionRulesUseCase(dl=dl, request=req).execute()

    def test_actor_not_in_case_raises_not_found(self, dl):
        """Unknown actor in the selected case raises VultronNotFoundError."""
        req = ActionRulesRequest(
            case_id=CASE_ID,
            actor_id="https://example.org/actors/unknown",
        )
        with pytest.raises(VultronNotFoundError):
            GetActionRulesUseCase(dl=dl, request=req).execute()

    def test_no_case_statuses_defaults(self, dl):
        """When case has no CaseStatus entries, EM/PXA default to None/pxa."""
        layer = TinyDbDataLayer(db_path=None)
        case = VulnerabilityCase(
            as_id=CASE_ID,
            name="Empty Status Case",
            actor_participant_index={ACTOR_ID: PARTICIPANT_ID},
            case_statuses=[],
        )
        layer.create(case)
        participant = CaseParticipant(
            as_id=PARTICIPANT_ID,
            attributed_to=ACTOR_ID,
            case_roles=[CVDRole.REPORTER],
            participant_statuses=[
                ParticipantStatus(
                    context=CASE_ID,
                    rm_state=RM.RECEIVED,
                    vfd_state=CS_vfd.Vfd,
                )
            ],
        )
        layer.create(participant)

        req = ActionRulesRequest(
            case_id=CASE_ID,
            actor_id=ACTOR_ID,
        )
        result = GetActionRulesUseCase(dl=layer, request=req).execute()

        assert result["em_state"] == EM.EMBARGO_MANAGEMENT_NONE
        assert result["pxa_state"] == CS_pxa.pxa.name

    def test_no_participant_statuses_defaults(self, dl):
        """When participant has no ParticipantStatus entries, RM/VFD default."""
        layer = TinyDbDataLayer(db_path=None)
        case = VulnerabilityCase(
            as_id=CASE_ID,
            name="Default Participant Status Case",
            actor_participant_index={ACTOR_ID: PARTICIPANT_ID},
            case_statuses=[CaseStatus(em_state=EM.NO_EMBARGO)],
        )
        layer.create(case)
        participant = CaseParticipant(
            as_id=PARTICIPANT_ID,
            attributed_to=ACTOR_ID,
            context=CASE_ID,
            case_roles=[CVDRole.FINDER],
            participant_statuses=[],
        )
        layer.create(participant)

        req = ActionRulesRequest(
            case_id=CASE_ID,
            actor_id=ACTOR_ID,
        )
        result = GetActionRulesUseCase(dl=layer, request=req).execute()

        assert result["rm_state"] == RM.START
        assert result["vfd_state"] == CS_vfd.vfd.name

    def test_em_state_variations(self, dl):
        """Different EM states are correctly reflected."""
        for em in [
            EM.NO_EMBARGO,
            EM.PROPOSED,
            EM.ACTIVE,
            EM.REVISE,
            EM.EXITED,
        ]:
            layer = TinyDbDataLayer(db_path=None)
            case = VulnerabilityCase(
                as_id=CASE_ID,
                actor_participant_index={ACTOR_ID: PARTICIPANT_ID},
                case_statuses=[CaseStatus(em_state=em, pxa_state=CS_pxa.pxa)],
            )
            layer.create(case)
            participant = CaseParticipant(
                as_id=PARTICIPANT_ID,
                attributed_to=ACTOR_ID,
                participant_statuses=[ParticipantStatus(context=CASE_ID)],
            )
            layer.create(participant)

            req = ActionRulesRequest(
                case_id=CASE_ID,
                actor_id=ACTOR_ID,
            )
            result = GetActionRulesUseCase(dl=layer, request=req).execute()
            assert (
                result["em_state"] == em
            ), f"Expected {em!r}, got {result['em_state']!r}"
