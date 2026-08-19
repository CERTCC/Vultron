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

"""Unit tests for ``CheckVendorRoleNode`` and ``CheckDeployerRoleNode``.

Both nodes gate VFD state transitions per CSB-15-001 and CSB-15-002:
- CheckVendorRoleNode: gates f→F (vfd_state=VFd); actor must hold CVDRole.VENDOR
- CheckDeployerRoleNode: gates d→D (vfd_state=VFD); actor must hold CVDRole.DEPLOYER
"""

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckDeployerRoleNode,
    CheckVendorRoleNode,
)
from vultron.core.models.vultron_types import VultronCase, VultronParticipant
from vultron.enums.roles import CVDRole

CASE_ID = "https://example.org/cases/case-001"
VENDOR_ACTOR_ID = "https://example.org/actors/vendor"
DEPLOYER_ACTOR_ID = "https://example.org/actors/deployer"
COORDINATOR_ACTOR_ID = "https://example.org/actors/coordinator"


@pytest.fixture
def vendor_participant() -> VultronParticipant:
    return VultronParticipant(
        id_="https://example.org/participants/vendor-cp-001",
        attributed_to=VENDOR_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.VENDOR],
    )


@pytest.fixture
def deployer_participant() -> VultronParticipant:
    return VultronParticipant(
        id_="https://example.org/participants/deployer-cp-001",
        attributed_to=DEPLOYER_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.DEPLOYER],
    )


@pytest.fixture
def coordinator_participant() -> VultronParticipant:
    return VultronParticipant(
        id_="https://example.org/participants/coordinator-cp-001",
        attributed_to=COORDINATOR_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.COORDINATOR],
    )


@pytest.fixture
def case_with_vendor_and_deployer(
    bt_scenario: BTTestScenario,
    vendor_participant: VultronParticipant,
    deployer_participant: VultronParticipant,
    coordinator_participant: VultronParticipant,
) -> VultronCase:
    case = VultronCase(
        id_=CASE_ID,
        name="Test Case",
        case_participants=[
            vendor_participant.id_,
            deployer_participant.id_,
            coordinator_participant.id_,
        ],
        actor_participant_index={
            VENDOR_ACTOR_ID: vendor_participant.id_,
            DEPLOYER_ACTOR_ID: deployer_participant.id_,
            COORDINATOR_ACTOR_ID: coordinator_participant.id_,
        },
    )
    bt_scenario.seed(
        vendor_participant, deployer_participant, coordinator_participant, case
    )
    return case


# ---------------------------------------------------------------------------
# CheckVendorRoleNode (CSB-15-001: gates f→F)
# ---------------------------------------------------------------------------


def test_vendor_guard_success_for_vendor_actor(
    bt_scenario: BTTestScenario,
    case_with_vendor_and_deployer: VultronCase,
) -> None:
    """SUCCESS when actor holds CVDRole.VENDOR (f→F allowed)."""
    result = bt_scenario.run(
        CheckVendorRoleNode(
            case_id=case_with_vendor_and_deployer.id_,
            actor_id=VENDOR_ACTOR_ID,
        ),
        actor_id=VENDOR_ACTOR_ID,
    )
    assert result.status == Status.SUCCESS


@pytest.mark.executes_as(DEPLOYER_ACTOR_ID)
def test_vendor_guard_failure_for_deployer_only_actor(
    bt_scenario: BTTestScenario,
    case_with_vendor_and_deployer: VultronCase,
) -> None:
    """FAILURE when actor holds CVDRole.DEPLOYER but not CVDRole.VENDOR."""
    result = bt_scenario.run(
        CheckVendorRoleNode(
            case_id=case_with_vendor_and_deployer.id_,
            actor_id=DEPLOYER_ACTOR_ID,
        ),
        actor_id=DEPLOYER_ACTOR_ID,
    )
    assert result.status == Status.FAILURE


@pytest.mark.executes_as(COORDINATOR_ACTOR_ID)
def test_vendor_guard_failure_for_coordinator_actor(
    bt_scenario: BTTestScenario,
    case_with_vendor_and_deployer: VultronCase,
) -> None:
    """FAILURE when actor holds CVDRole.COORDINATOR (no VENDOR)."""
    result = bt_scenario.run(
        CheckVendorRoleNode(
            case_id=case_with_vendor_and_deployer.id_,
            actor_id=COORDINATOR_ACTOR_ID,
        ),
        actor_id=COORDINATOR_ACTOR_ID,
    )
    assert result.status == Status.FAILURE


def test_vendor_guard_failure_when_case_missing(
    bt_scenario: BTTestScenario,
) -> None:
    """FAILURE when the case record is absent from the DataLayer."""
    result = bt_scenario.run(
        CheckVendorRoleNode(case_id=CASE_ID, actor_id=VENDOR_ACTOR_ID),
        actor_id=VENDOR_ACTOR_ID,
    )
    assert result.status == Status.FAILURE


def test_vendor_guard_failure_when_actor_not_in_case(
    bt_scenario: BTTestScenario,
    vendor_participant: VultronParticipant,
) -> None:
    """FAILURE when actor_id is not present in actor_participant_index."""
    case = VultronCase(
        id_=CASE_ID,
        name="Test Case",
        case_participants=[vendor_participant.id_],
        actor_participant_index={VENDOR_ACTOR_ID: vendor_participant.id_},
    )
    bt_scenario.seed(vendor_participant, case)

    unknown_actor = "https://example.org/actors/unknown"
    result = bt_scenario.run(
        CheckVendorRoleNode(case_id=CASE_ID, actor_id=unknown_actor),
        actor_id=unknown_actor,
    )
    assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# CheckDeployerRoleNode (CSB-15-002: gates d→D)
# ---------------------------------------------------------------------------


@pytest.mark.executes_as(DEPLOYER_ACTOR_ID)
def test_deployer_guard_success_for_deployer_actor(
    bt_scenario: BTTestScenario,
    case_with_vendor_and_deployer: VultronCase,
) -> None:
    """SUCCESS when actor holds CVDRole.DEPLOYER (d→D allowed)."""
    result = bt_scenario.run(
        CheckDeployerRoleNode(
            case_id=case_with_vendor_and_deployer.id_,
            actor_id=DEPLOYER_ACTOR_ID,
        ),
        actor_id=DEPLOYER_ACTOR_ID,
    )
    assert result.status == Status.SUCCESS


def test_deployer_guard_failure_for_vendor_only_actor(
    bt_scenario: BTTestScenario,
    case_with_vendor_and_deployer: VultronCase,
) -> None:
    """FAILURE when actor holds CVDRole.VENDOR but not CVDRole.DEPLOYER (CSB-15-002)."""
    result = bt_scenario.run(
        CheckDeployerRoleNode(
            case_id=case_with_vendor_and_deployer.id_,
            actor_id=VENDOR_ACTOR_ID,
        ),
        actor_id=VENDOR_ACTOR_ID,
    )
    assert result.status == Status.FAILURE


@pytest.mark.executes_as(COORDINATOR_ACTOR_ID)
def test_deployer_guard_failure_for_coordinator_actor(
    bt_scenario: BTTestScenario,
    case_with_vendor_and_deployer: VultronCase,
) -> None:
    """FAILURE when actor holds CVDRole.COORDINATOR (no DEPLOYER)."""
    result = bt_scenario.run(
        CheckDeployerRoleNode(
            case_id=case_with_vendor_and_deployer.id_,
            actor_id=COORDINATOR_ACTOR_ID,
        ),
        actor_id=COORDINATOR_ACTOR_ID,
    )
    assert result.status == Status.FAILURE


@pytest.mark.executes_as(DEPLOYER_ACTOR_ID)
def test_deployer_guard_failure_when_case_missing(
    bt_scenario: BTTestScenario,
) -> None:
    """FAILURE when the case record is absent from the DataLayer."""
    result = bt_scenario.run(
        CheckDeployerRoleNode(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID),
        actor_id=DEPLOYER_ACTOR_ID,
    )
    assert result.status == Status.FAILURE


def test_deployer_guard_failure_when_actor_not_in_case(
    bt_scenario: BTTestScenario,
    deployer_participant: VultronParticipant,
) -> None:
    """FAILURE when actor_id is not present in actor_participant_index."""
    case = VultronCase(
        id_=CASE_ID,
        name="Test Case",
        case_participants=[deployer_participant.id_],
        actor_participant_index={DEPLOYER_ACTOR_ID: deployer_participant.id_},
    )
    bt_scenario.seed(deployer_participant, case)

    unknown_actor = "https://example.org/actors/unknown"
    result = bt_scenario.run(
        CheckDeployerRoleNode(case_id=CASE_ID, actor_id=unknown_actor),
        actor_id=unknown_actor,
    )
    assert result.status == Status.FAILURE
