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

from types import SimpleNamespace

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.case_owner import CASE_OWNER_ID
from test.support.objects import make
from vultron.core.behaviors.case.nodes.conditions import (
    CheckIsCaseManagerNode,
)
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole

CASE_ID = "https://example.org/cases/case-001"
MANAGER_ACTOR_ID = "https://example.org/actors/coordinator"
NON_MANAGER_ACTOR_ID = "https://example.org/actors/vendor"


@pytest.fixture
def case_manager_participant() -> CaseParticipant:
    return make(
        CaseParticipant,
        id_="https://example.org/participants/coordinator-cp-001",
        attributed_to=MANAGER_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER, CVDRole.COORDINATOR],
    )


@pytest.fixture
def vendor_participant() -> CaseParticipant:
    return make(
        CaseParticipant,
        id_="https://example.org/participants/vendor-cp-001",
        attributed_to=NON_MANAGER_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.VENDOR],
    )


@pytest.fixture
def case_with_manager(
    bt_scenario: BTTestScenario,
    case_manager_participant: CaseParticipant,
    vendor_participant: CaseParticipant,
) -> VulnerabilityCase:
    case = make(
        VulnerabilityCase,
        attributed_to=CASE_OWNER_ID,
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


@pytest.mark.executes_as(MANAGER_ACTOR_ID)
def test_returns_success_when_actor_is_case_manager(
    bt_scenario: BTTestScenario, case_with_manager: VulnerabilityCase
) -> None:
    result = bt_scenario.run(
        with_case_id(CheckIsCaseManagerNode(), case_with_manager.id_),
        actor_id=MANAGER_ACTOR_ID,
    )
    assert result.status == Status.SUCCESS


def test_returns_failure_when_actor_is_not_case_manager(
    bt_scenario: BTTestScenario, case_with_manager: VulnerabilityCase
) -> None:
    result = bt_scenario.run(
        with_case_id(CheckIsCaseManagerNode(), case_with_manager.id_),
        actor_id=NON_MANAGER_ACTOR_ID,
    )
    assert result.status == Status.FAILURE


@pytest.mark.executes_as(MANAGER_ACTOR_ID)
def test_returns_failure_when_case_is_missing(
    bt_scenario: BTTestScenario,
) -> None:
    result = bt_scenario.run(
        with_case_id(CheckIsCaseManagerNode(), CASE_ID),
        actor_id=MANAGER_ACTOR_ID,
    )
    assert result.status == Status.FAILURE


@pytest.mark.executes_as(MANAGER_ACTOR_ID)
def test_returns_failure_when_case_has_no_case_manager(
    bt_scenario: BTTestScenario, vendor_participant: CaseParticipant
) -> None:
    case = make(
        VulnerabilityCase,
        attributed_to=CASE_OWNER_ID,
        id_=CASE_ID,
        name="Test Case",
        case_participants=[vendor_participant.id_],
        actor_participant_index={
            NON_MANAGER_ACTOR_ID: vendor_participant.id_,
        },
    )
    bt_scenario.seed(vendor_participant, case)

    result = bt_scenario.run(
        with_case_id(CheckIsCaseManagerNode(), case.id_),
        actor_id=MANAGER_ACTOR_ID,
    )
    assert result.status == Status.FAILURE


@pytest.mark.executes_as(MANAGER_ACTOR_ID)
def test_sets_case_actor_id_output_on_success(
    bt_scenario: BTTestScenario, case_with_manager: VulnerabilityCase
) -> None:
    """``/case_actor_id`` is published for later nodes of the same execution
    and does not outlive it (#5803).
    """
    _, published = bt_scenario.run_capturing(
        with_case_id(CheckIsCaseManagerNode(), case_with_manager.id_),
        "case_actor_id",
        actor_id=MANAGER_ACTOR_ID,
    )
    assert published == MANAGER_ACTOR_ID
    assert "/case_actor_id" not in py_trees.blackboard.Blackboard.storage


@pytest.mark.executes_as(MANAGER_ACTOR_ID)
def test_resolves_case_id_from_activity_log_entry(
    bt_scenario: BTTestScenario, case_with_manager: VulnerabilityCase
) -> None:
    activity = SimpleNamespace(
        log_entry=SimpleNamespace(case_id=case_with_manager.id_)
    )
    result = bt_scenario.run(
        CheckIsCaseManagerNode(),
        actor_id=MANAGER_ACTOR_ID,
        activity=activity,
    )
    assert result.status == Status.SUCCESS
