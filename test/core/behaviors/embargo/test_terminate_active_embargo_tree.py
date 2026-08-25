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
"""Tests for create_terminate_active_embargo_tree (EMB-14).

Verifies:
- Tree structure: Sequence root with correct sub-tree shape.
- Call-out injection: bundle factories are wired at each call-out slot.
- Deterministic defaults: ceiling/floor rule applied per BT-23-002.
- Stochastic bundle: produces the expected fuzzer classes.
- terminate_embargo_bt delegation: final child is the existing mechanism.
"""

import pytest
import py_trees

from vultron.core.behaviors.embargo.terminate_active_embargo_tree import (
    create_terminate_active_embargo_tree,
)
from vultron.core.behaviors.embargo.nodes import HasActiveEmbargoNode
from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.core.behaviors.call_out.bundles.embargo import (
    EMBARGO_DETERMINISTIC,
    EmbargoCallOutBundle,
)
from vultron.demo.fuzzer.bundles.embargo import EMBARGO_STOCHASTIC
from vultron.demo.fuzzer.embargo import (
    EmbargoExitOverride,
    EmbargoExitPolicyGuard,
    ExitEmbargoForOtherReason,
    ExitEmbargoWhenDeployed,
    ExitEmbargoWhenFixReady,
    OnEmbargoExit,
)

CASE_ID = "https://example.org/cases/test-terminate-001"


def _make_result_out() -> dict:
    return {}


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------


def test_returns_behaviour():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_root_name():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert tree.name == "TerminateActiveEmbargoBT"


def test_root_is_sequence():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert isinstance(tree, py_trees.composites.Sequence)


def test_root_has_five_children():
    """Root Sequence: HasActiveEmbargo, ReasonSelector, AuthorizeSelector, OnEmbargoExit, terminate_embargo_bt."""
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert len(tree.children) == 5


def test_root_sequence_memory_false():
    """memory=False on root ensures stateless restart every tick."""
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert isinstance(tree, py_trees.composites.Sequence)
    assert tree.memory is False


def test_reason_selector_memory_false():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    reason = tree.children[1]
    assert isinstance(reason, py_trees.composites.Selector)
    assert reason.memory is False


def test_authorize_selector_memory_false():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    auth = tree.children[2]
    assert isinstance(auth, py_trees.composites.Selector)
    assert auth.memory is False


# ---------------------------------------------------------------------------
# Child 0 — HasActiveEmbargoNode precondition guard
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-14-001")
def test_child_0_is_has_active_embargo():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert isinstance(tree.children[0], HasActiveEmbargoNode)


# ---------------------------------------------------------------------------
# Child 1 — ReasonSelector (EMB-14-001)
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-14-001")
def test_child_1_is_reason_selector():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    reason = tree.children[1]
    assert isinstance(reason, py_trees.composites.Selector)
    assert reason.name == "ReasonSelector"


@pytest.mark.spec("EMB-14-001")
def test_reason_selector_has_three_children():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert len(tree.children[1].children) == 3


@pytest.mark.spec("EMB-14-001")
@pytest.mark.parametrize(
    "index,cls",
    [
        (0, AlwaysFail),  # ExitEmbargoWhenDeployed (p=0.33)
        (1, AlwaysFail),  # ExitEmbargoWhenFixReady (p=0.25)
        (2, AlwaysFail),  # ExitEmbargoForOtherReason (p=0.005)
    ],
)
def test_reason_selector_deterministic_defaults(index, cls):
    """DETERMINISTIC: all reason nodes are AlwaysFail (p < 0.5 for all three)."""
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert isinstance(tree.children[1].children[index], cls)


@pytest.mark.spec("EMB-14-001")
@pytest.mark.parametrize(
    "index,cls",
    [
        (0, ExitEmbargoWhenDeployed),
        (1, ExitEmbargoWhenFixReady),
        (2, ExitEmbargoForOtherReason),
    ],
)
def test_reason_selector_stochastic_classes(index, cls):
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID,
        result_out=_make_result_out(),
        call_out=EMBARGO_STOCHASTIC,
    )
    assert isinstance(tree.children[1].children[index], cls)


# ---------------------------------------------------------------------------
# Child 2 — AuthorizeEmbargoExit Selector (EMB-14-002, EMB-14-003)
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-14-002")
def test_child_2_is_authorize_selector():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    auth = tree.children[2]
    assert isinstance(auth, py_trees.composites.Selector)
    assert auth.name == "AuthorizeEmbargoExit"


@pytest.mark.spec("EMB-14-002")
@pytest.mark.spec("EMB-14-003")
def test_authorize_selector_has_two_children():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert len(tree.children[2].children) == 2


@pytest.mark.spec("EMB-14-002")
def test_authorize_first_child_deterministic_is_always_succeed():
    """EmbargoExitPolicyGuard (p=1.0) → AlwaysSucceed."""
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert isinstance(tree.children[2].children[0], AlwaysSucceed)


@pytest.mark.spec("EMB-14-003")
def test_authorize_second_child_deterministic_is_always_fail():
    """EmbargoExitOverride (p=0.0) → AlwaysFail."""
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert isinstance(tree.children[2].children[1], AlwaysFail)


@pytest.mark.spec("EMB-14-002")
def test_authorize_first_child_stochastic_is_policy_guard():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID,
        result_out=_make_result_out(),
        call_out=EMBARGO_STOCHASTIC,
    )
    assert isinstance(tree.children[2].children[0], EmbargoExitPolicyGuard)


@pytest.mark.spec("EMB-14-003")
def test_authorize_second_child_stochastic_is_override():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID,
        result_out=_make_result_out(),
        call_out=EMBARGO_STOCHASTIC,
    )
    assert isinstance(tree.children[2].children[1], EmbargoExitOverride)


# ---------------------------------------------------------------------------
# Child 3 — OnEmbargoExit Actuator
# ---------------------------------------------------------------------------


def test_child_3_on_embargo_exit_deterministic_is_always_succeed():
    """OnEmbargoExit (p=1.0) → AlwaysSucceed in DETERMINISTIC bundle."""
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert isinstance(tree.children[3], AlwaysSucceed)


def test_child_3_on_embargo_exit_stochastic_class():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID,
        result_out=_make_result_out(),
        call_out=EMBARGO_STOCHASTIC,
    )
    assert isinstance(tree.children[3], OnEmbargoExit)


# ---------------------------------------------------------------------------
# Child 4 — terminate_embargo_bt delegation
# ---------------------------------------------------------------------------


def test_child_4_is_terminate_embargo_bt_sequence():
    """The final child must be the TerminateEmbargoBT Sequence (BT-19-001)."""
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    term = tree.children[4]
    assert isinstance(term, py_trees.composites.Sequence)
    assert term.name == "TerminateEmbargoBT"


# ---------------------------------------------------------------------------
# Factory injection — each call-out slot accepts a custom factory
# ---------------------------------------------------------------------------


_TERMINATE_FACTORY_FIELDS = [
    ("exit_embargo_when_deployed_factory", 1, 0),
    ("exit_embargo_when_fix_ready_factory", 1, 1),
    ("exit_embargo_for_other_reason_factory", 1, 2),
    ("embargo_exit_policy_guard_factory", 2, 0),
    ("embargo_exit_override_factory", 2, 1),
    ("on_embargo_exit_factory", None, None),  # direct child 3
]


@pytest.mark.parametrize(
    "field,parent_idx,child_idx", _TERMINATE_FACTORY_FIELDS
)
def test_factory_field_is_wired(field, parent_idx, child_idx):
    sentinel = {"called": False}

    def custom_factory(name: str) -> py_trees.behaviour.Behaviour:
        sentinel["called"] = True

        class _Marker(py_trees.behaviour.Behaviour):
            IS_CUSTOM_MARKER = True

            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name=name)

    bundle = EmbargoCallOutBundle(**{field: custom_factory})  # type: ignore[arg-type]
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out(), call_out=bundle
    )
    assert sentinel["called"], f"factory {field!r} was not called"

    if parent_idx is None:
        # on_embargo_exit is child 3 directly
        assert getattr(tree.children[3], "IS_CUSTOM_MARKER", False)
    else:
        node = tree.children[parent_idx].children[child_idx]
        assert getattr(node, "IS_CUSTOM_MARKER", False)


# ---------------------------------------------------------------------------
# result_out propagation
# ---------------------------------------------------------------------------


def test_result_out_passed_through():
    """result_out dict is the same object passed to HasActiveEmbargoNode."""
    result = _make_result_out()
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=result
    )
    guard = tree.children[0]
    assert isinstance(guard, HasActiveEmbargoNode)
    # HasActiveEmbargoNode stores result_out as an instance attribute
    assert guard._result_out is result


# ---------------------------------------------------------------------------
# Deterministic singleton accepted
# ---------------------------------------------------------------------------


def test_deterministic_singleton_accepted():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID,
        result_out=_make_result_out(),
        call_out=EMBARGO_DETERMINISTIC,
    )
    assert isinstance(tree, py_trees.behaviour.Behaviour)
