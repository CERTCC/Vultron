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

"""Tests for ``create_case_manager_gated_tree`` (BTND-07-005).

The gate's whole reason for existing is that it keeps *two* FAILURE modes apart:
"I am not the case manager, so skip" and "I am the case manager and the work
failed". The hand-rolled shape BTND-07-005 forbids —
``Selector[Sequence[check, *children], Success]`` — collapses them, reporting a
genuine failure as a benign skip. So the load-bearing assertion here is
:meth:`TestCaseManagerGate.test_a_failure_by_the_case_manager_is_not_masked`;
everything else establishes that the skip path still works.

Structural assertions are included on purpose: the ``Inverter`` is what separates
the two modes, so its presence is a behavioural fact, not a formatting detail.
"""

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.models.vultron_types import VultronCase, VultronParticipant
from vultron.enums.roles import CVDRole

CASE_ID = "https://example.org/cases/case-gate-001"
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
def case_with_manager(bt_scenario: BTTestScenario) -> VultronCase:
    manager = VultronParticipant(
        id_="https://example.org/participants/coordinator-gate-001",
        attributed_to=MANAGER_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER, CVDRole.COORDINATOR],
    )
    vendor = VultronParticipant(
        id_="https://example.org/participants/vendor-gate-001",
        attributed_to=NON_MANAGER_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.VENDOR],
    )
    case = VultronCase(
        id_=CASE_ID,
        name="Gated Case",
        case_participants=[manager.id_, vendor.id_],
        actor_participant_index={
            MANAGER_ACTOR_ID: manager.id_,
            NON_MANAGER_ACTOR_ID: vendor.id_,
        },
    )
    bt_scenario.seed(manager, vendor, case)
    return case


class TestCaseManagerGate:
    @pytest.mark.executes_as(MANAGER_ACTOR_ID)
    def test_the_case_manager_runs_the_children(
        self, bt_scenario: BTTestScenario, case_with_manager: VultronCase
    ) -> None:
        child = _Spy("Work")
        result = bt_scenario.run(
            create_case_manager_gated_tree("Gate", CASE_ID, [child]),
            actor_id=MANAGER_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS
        assert child.ticks == 1

    def test_a_non_manager_skips_without_running_the_children(
        self, bt_scenario: BTTestScenario, case_with_manager: VultronCase
    ) -> None:
        """SUCCESS here means "not my job", and must not run the work."""
        child = _Spy("Work")
        result = bt_scenario.run(
            create_case_manager_gated_tree("Gate", CASE_ID, [child]),
            actor_id=NON_MANAGER_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS
        assert child.ticks == 0

    @pytest.mark.executes_as(MANAGER_ACTOR_ID)
    def test_a_failure_by_the_case_manager_is_not_masked(
        self, bt_scenario: BTTestScenario, case_with_manager: VultronCase
    ) -> None:
        """The reason BTND-07-005 forbids the hand-rolled form.

        With a trailing ``Success`` fallback instead of the ``Inverter``, this
        would return SUCCESS — a canonical ledger commit that silently did not
        commit. The child must have run *and* the root must report FAILURE.
        """
        child = _Spy("Work", Status.FAILURE)
        result = bt_scenario.run(
            create_case_manager_gated_tree("Gate", CASE_ID, [child]),
            actor_id=MANAGER_ACTOR_ID,
        )
        assert child.ticks == 1, "the gate opened, so the work must have run"
        assert result.status == Status.FAILURE

    @pytest.mark.executes_as(MANAGER_ACTOR_ID)
    def test_a_mid_sequence_failure_propagates(
        self, bt_scenario: BTTestScenario, case_with_manager: VultronCase
    ) -> None:
        """Multiple children are a Sequence, so a partial run is a failure.

        Without this, a two-step commit whose first step succeeded and second
        failed would look like a completed commit.
        """
        first = _Spy("First")
        second = _Spy("Second", Status.FAILURE)
        third = _Spy("Third")
        result = bt_scenario.run(
            create_case_manager_gated_tree(
                "Gate", CASE_ID, [first, second, third]
            ),
            actor_id=MANAGER_ACTOR_ID,
        )
        assert result.status == Status.FAILURE
        assert (first.ticks, second.ticks, third.ticks) == (1, 1, 0)

    @pytest.mark.executes_as(MANAGER_ACTOR_ID)
    def test_a_missing_case_does_not_open_the_gate(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """No case means no CASE_MANAGER to be, so the work must not run.

        The gate reports SUCCESS because "not the case manager" is the honest
        reading of an absent case; what matters is that the children stay unrun.
        """
        child = _Spy("Work")
        result = bt_scenario.run(
            create_case_manager_gated_tree("Gate", CASE_ID, [child]),
            actor_id=MANAGER_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS
        assert child.ticks == 0


class TestGateStructure:
    """BTND-07-005 is a shape requirement, so the shape is asserted."""

    def test_the_gate_is_an_inverter_not_a_success_fallback(self) -> None:
        root = create_case_manager_gated_tree("Gate", CASE_ID, [_Spy("Work")])
        skip_branch = root.children[0]

        assert isinstance(root, py_trees.composites.Selector)
        assert root.name == "Gate"
        assert skip_branch.name == "SkipIfNotCaseManager"
        assert isinstance(
            skip_branch.children[0], py_trees.decorators.Inverter
        )
        assert not any(
            isinstance(child, py_trees.behaviours.Success)
            for child in root.children
        ), "a Success fallback is the masking shape BTND-07-005 forbids"

    def test_a_lone_child_is_not_wrapped(self) -> None:
        """A wrapper would add a tick layer without adding a guarantee."""
        child = _Spy("Work")
        root = create_case_manager_gated_tree("Gate", CASE_ID, [child])
        assert root.children[1] is child

    def test_several_children_become_a_sequence(self) -> None:
        root = create_case_manager_gated_tree(
            "Gate", CASE_ID, [_Spy("A"), _Spy("B")]
        )
        body = root.children[1]
        assert isinstance(body, py_trees.composites.Sequence)
        assert body.name == "GateBody"

    def test_the_body_name_can_be_overridden(self) -> None:
        root = create_case_manager_gated_tree(
            "Gate", CASE_ID, [_Spy("A"), _Spy("B")], body_name="CommitSteps"
        )
        assert root.children[1].name == "CommitSteps"

    @pytest.mark.parametrize("memory_owner", [0, 1])
    def test_no_composite_uses_memory(self, memory_owner: int) -> None:
        """A memoried Selector would latch the skip branch across ticks.

        Once skipped, the gate would never re-evaluate — an actor that *became*
        the case manager mid-case (ownership transfer) would stay locked out.
        """
        root = create_case_manager_gated_tree(
            "Gate", CASE_ID, [_Spy("A"), _Spy("B")]
        )
        node = [root, root.children[1]][memory_owner]
        # ``memory`` lives on Selector/Sequence, not on Composite — so narrowing
        # is also the assertion that the gate is built from those two.
        assert isinstance(
            node, (py_trees.composites.Selector, py_trees.composites.Sequence)
        ), f"{node.name} carries no memory flag to check"
        assert node.memory is False
