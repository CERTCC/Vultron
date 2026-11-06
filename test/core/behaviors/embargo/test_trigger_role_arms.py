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

"""The role fork every trigger-side embargo tree ends with (BT-17-001).

A trigger runs on the actor's own initiative, so no received path chose it and
``_skip_at_case_manager`` reads the role itself — the one place that still
does, now that ADR-0153 gives every declaring received tree a path stage to
read instead.  The load-bearing facts are that exactly one arm runs for any
actor and that the non-manager arm's FAILURE is not masked: the first child is
a pure condition, so a Selector that falls through reports the work's FAILURE
as its own.
"""

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.case_owner import CASE_OWNER_ID
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.embargo.trigger_tree._arms import (
    _skip_at_case_manager,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole

CASE_ID = "https://example.org/cases/trigger-arm-001"
MANAGER_ACTOR_ID = "https://example.org/actors/coordinator"
NON_MANAGER_ACTOR_ID = "https://example.org/actors/vendor"


class _Spy(py_trees.behaviour.Behaviour):
    """A child that records whether it ran and returns a fixed status."""

    def __init__(self, name: str, status: Status = Status.SUCCESS) -> None:
        super().__init__(name=name)
        self._status = status
        self.ticks = 0

    def update(self) -> Status:
        self.ticks += 1
        return self._status


@pytest.fixture
def case_with_manager(bt_scenario: BTTestScenario) -> VulnerabilityCase:
    manager = CaseParticipant(
        id_="https://example.org/participants/coordinator-arm-001",
        attributed_to=MANAGER_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER, CVDRole.COORDINATOR],
    )
    vendor = CaseParticipant(
        id_="https://example.org/participants/vendor-arm-001",
        attributed_to=NON_MANAGER_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.VENDOR],
    )
    case = VulnerabilityCase(
        attributed_to=CASE_OWNER_ID,
        id_=CASE_ID,
        name="Trigger Arm Case",
        case_participants=[manager.id_, vendor.id_],
        actor_participant_index={
            MANAGER_ACTOR_ID: manager.id_,
            NON_MANAGER_ACTOR_ID: vendor.id_,
        },
    )
    bt_scenario.seed(manager, vendor, case)
    return case


class TestTriggerNonManagerArm:
    """The arm that runs the work for everyone *but* the CASE_MANAGER."""

    @pytest.mark.executes_as(MANAGER_ACTOR_ID)
    def test_the_case_manager_skips_without_running_the_children(
        self, bt_scenario: BTTestScenario, case_with_manager: VulnerabilityCase
    ) -> None:
        child = _Spy("ReplicaWork")
        result = bt_scenario.run(
            _skip_at_case_manager("Gate", CASE_ID, [child]),
            actor_id=MANAGER_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS
        assert child.ticks == 0

    @pytest.mark.executes_as(NON_MANAGER_ACTOR_ID)
    def test_a_non_manager_runs_the_children(
        self, bt_scenario: BTTestScenario, case_with_manager: VulnerabilityCase
    ) -> None:
        child = _Spy("ReplicaWork")
        result = bt_scenario.run(
            _skip_at_case_manager("Gate", CASE_ID, [child]),
            actor_id=NON_MANAGER_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS
        assert child.ticks == 1

    @pytest.mark.executes_as(NON_MANAGER_ACTOR_ID)
    def test_a_failure_by_a_non_manager_is_not_masked(
        self, bt_scenario: BTTestScenario, case_with_manager: VulnerabilityCase
    ) -> None:
        """The first arm is a pure condition, so the work's FAILURE is the gate's."""
        child = _Spy("ReplicaWork", Status.FAILURE)
        result = bt_scenario.run(
            _skip_at_case_manager("Gate", CASE_ID, [child]),
            actor_id=NON_MANAGER_ACTOR_ID,
        )
        assert child.ticks == 1
        assert result.status == Status.FAILURE

    @pytest.mark.executes_as(NON_MANAGER_ACTOR_ID)
    def test_the_two_gates_are_mutually_exclusive(
        self, bt_scenario: BTTestScenario, case_with_manager: VulnerabilityCase
    ) -> None:
        """Side by side in one Sequence, exactly one arm runs for any actor."""
        manager_work = _Spy("ManagerWork")
        replica_work = _Spy("ReplicaWork")
        tree = py_trees.composites.Sequence(
            name="Both",
            memory=False,
            children=[
                create_case_manager_gated_tree(
                    "ManagerGate", CASE_ID, [manager_work]
                ),
                _skip_at_case_manager("ReplicaGate", CASE_ID, [replica_work]),
            ],
        )
        result = bt_scenario.run(tree, actor_id=NON_MANAGER_ACTOR_ID)
        assert result.status == Status.SUCCESS
        assert (manager_work.ticks, replica_work.ticks) == (0, 1)

    @pytest.mark.executes_as(NON_MANAGER_ACTOR_ID)
    def test_a_case_with_no_role_holder_runs_the_replica_arm_only(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """CM-02-014 says a case always has a CASE_MANAGER; pin the gates anyway.

        With nobody holding the role, ``CheckIsCaseManagerNode`` fails, so the
        manager arm skips and the replica arm runs — never both skip, never
        both run.  A future change to the condition node that made both arms
        skip would silently drop every effect of a received tree.
        """
        vendor = CaseParticipant(
            id_="https://example.org/participants/vendor-arm-002",
            attributed_to=NON_MANAGER_ACTOR_ID,
            context=CASE_ID,
            case_roles=[CVDRole.VENDOR],
        )
        case = VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_=CASE_ID,
            name="No manager",
            case_participants=[vendor.id_],
            actor_participant_index={NON_MANAGER_ACTOR_ID: vendor.id_},
        )
        bt_scenario.seed(vendor, case)
        manager_work, replica_work = _Spy("ManagerWork"), _Spy("ReplicaWork")
        result = bt_scenario.run(
            _both_gates(manager_work, replica_work),
            actor_id=NON_MANAGER_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS
        assert (manager_work.ticks, replica_work.ticks) == (0, 1)

    @pytest.mark.executes_as(NON_MANAGER_ACTOR_ID)
    def test_a_store_without_the_case_runs_the_replica_arm_only(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """A replica that does not hold the case yet still records what arrived."""
        manager_work, replica_work = _Spy("ManagerWork"), _Spy("ReplicaWork")
        result = bt_scenario.run(
            _both_gates(manager_work, replica_work),
            actor_id=NON_MANAGER_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS
        assert (manager_work.ticks, replica_work.ticks) == (0, 1)


def _both_gates(
    manager_work: py_trees.behaviour.Behaviour,
    replica_work: py_trees.behaviour.Behaviour,
) -> py_trees.composites.Sequence:
    """The two gates side by side, as a received tree composes them."""
    return py_trees.composites.Sequence(
        name="Both",
        memory=False,
        children=[
            create_case_manager_gated_tree(
                "ManagerGate", CASE_ID, [manager_work]
            ),
            _skip_at_case_manager("ReplicaGate", CASE_ID, [replica_work]),
        ],
    )
