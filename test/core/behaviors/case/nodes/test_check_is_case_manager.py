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

"""Unit tests for ``CheckIsCaseManagerNode``."""

import pytest
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.conditions import (
    CheckIsCaseManagerNode,
)
from vultron.core.models.vultron_types import VultronCase, VultronParticipant
from vultron.enums.roles import CVDRole
from test.core.behaviors.bt_harness import BTTestScenario

CASE_ID = "https://example.org/cases/case-001"
MANAGER_ACTOR_ID = "https://example.org/actors/coordinator"
NON_MANAGER_ACTOR_ID = "https://example.org/actors/vendor"


@pytest.fixture
def case_manager_participant() -> VultronParticipant:
    return VultronParticipant(
        id_="https://example.org/participants/coordinator-cp-001",
        attributed_to=MANAGER_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER, CVDRole.COORDINATOR],
    )


@pytest.fixture
def vendor_participant() -> VultronParticipant:
    return VultronParticipant(
        id_="https://example.org/participants/vendor-cp-001",
        attributed_to=NON_MANAGER_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.VENDOR],
    )


@pytest.fixture
def case_with_manager(
    bt_scenario: BTTestScenario,
    case_manager_participant: VultronParticipant,
    vendor_participant: VultronParticipant,
) -> VultronCase:
    case = VultronCase(
        id_=CASE_ID,
        name="Test Case",
        case_participants=[
            case_manager_participant.id_,
            vendor_participant.id_,
        ],
        actor_participant_index={
            MANAGER_ACTOR_ID: case_manager_participant.id_,
            NON_MANAGER_ACTOR_ID: vendor_participant.id_,
        },
    )
    bt_scenario.seed(case_manager_participant, vendor_participant, case)
    return case


def test_returns_success_when_actor_is_case_manager(
    bt_scenario: BTTestScenario, case_with_manager: VultronCase
) -> None:
    result = bt_scenario.run(
        CheckIsCaseManagerNode(case_id=case_with_manager.id_),
        actor_id=MANAGER_ACTOR_ID,
    )
    assert result.status == Status.SUCCESS


def test_returns_failure_when_actor_is_not_case_manager(
    bt_scenario: BTTestScenario, case_with_manager: VultronCase
) -> None:
    result = bt_scenario.run(
        CheckIsCaseManagerNode(case_id=case_with_manager.id_),
        actor_id=NON_MANAGER_ACTOR_ID,
    )
    assert result.status == Status.FAILURE


def test_returns_failure_when_case_is_missing(
    bt_scenario: BTTestScenario,
) -> None:
    result = bt_scenario.run(
        CheckIsCaseManagerNode(case_id=CASE_ID),
        actor_id=MANAGER_ACTOR_ID,
    )
    assert result.status == Status.FAILURE


def test_returns_failure_when_case_has_no_case_manager(
    bt_scenario: BTTestScenario, vendor_participant: VultronParticipant
) -> None:
    case = VultronCase(
        id_=CASE_ID,
        name="Test Case",
        case_participants=[vendor_participant.id_],
        actor_participant_index={
            NON_MANAGER_ACTOR_ID: vendor_participant.id_,
        },
    )
    bt_scenario.seed(vendor_participant, case)

    result = bt_scenario.run(
        CheckIsCaseManagerNode(case_id=case.id_),
        actor_id=MANAGER_ACTOR_ID,
    )
    assert result.status == Status.FAILURE
