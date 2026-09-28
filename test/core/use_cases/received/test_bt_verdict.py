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

"""Tests for the received-side BT verdict helper (#2255)."""

import py_trees
import pytest
from py_trees.common import Status

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTExecutionResult
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
    failure_reason,
    find_named,
    find_node,
    node_failed,
    node_succeeded,
    not_case_manager_refusal,
    verdict_from_bt,
)
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


class _Fixed(py_trees.behaviour.Behaviour):
    def __init__(self, name: str, status: Status, message: str = "") -> None:
        super().__init__(name=name)
        self._status = status
        self._message = message

    def update(self) -> Status:
        self.feedback_message = self._message
        return self._status


class _Guard(_Fixed):
    pass


def _ran(
    *children: py_trees.behaviour.Behaviour,
) -> py_trees.behaviour.Behaviour:
    root = py_trees.composites.Sequence(name="Root", memory=False)
    root.add_children(list(children))
    root.tick_once()
    return root


def test_success_is_applied():
    tree = _ran(_Fixed("Ok", Status.SUCCESS))
    verdict = verdict_from_bt(
        tree, BTExecutionResult(status=Status.SUCCESS), label="TestBT"
    )
    assert verdict.disposition == HandlerDisposition.APPLIED


def test_failure_is_refused_with_leaf_reason():
    tree = _ran(_Fixed("Check", Status.FAILURE, "sender is not a participant"))
    verdict = verdict_from_bt(
        tree,
        BTExecutionResult(status=Status.FAILURE, feedback_message="root"),
        label="TestBT",
    )
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == "TestBT: sender is not a participant"


def test_raised_node_reason_comes_from_result():
    """A node that raised has no status, so only the bridge saw the reason."""
    tree = py_trees.composites.Sequence(name="Root", memory=False)
    tree.add_child(_Fixed("Never", Status.SUCCESS))
    result = BTExecutionResult(
        status=Status.FAILURE,
        feedback_message="BT execution failed: VultronError: boom",
    )
    assert failure_reason(tree, result) == result.feedback_message


def test_internal_error_raises():
    tree = _ran(_Fixed("Check", Status.FAILURE))
    with pytest.raises(VultronBTInternalError, match="TestBT"):
        verdict_from_bt(
            tree,
            BTExecutionResult(
                status=Status.FAILURE,
                feedback_message="KeyError: x",
                internal_error=True,
            ),
            label="TestBT",
        )


def test_leader_skip_is_skipped():
    tree = py_trees.composites.Sequence(name="Root", memory=False)
    verdict = verdict_from_bt(
        tree,
        BTExecutionResult(status=Status.FAILURE, leader_skipped=True),
        label="TestBT",
    )
    assert verdict.disposition == HandlerDisposition.SKIPPED


def test_node_lookup_by_type_accepts_tree_wrapper():
    guard = _Guard("Guard", Status.FAILURE, "already stored")
    root = py_trees.composites.Selector(name="Root", memory=False)
    root.add_children([guard, _Fixed("Work", Status.SUCCESS)])
    wrapper = py_trees.trees.BehaviourTree(root)
    wrapper.tick()
    assert find_node(wrapper, _Guard) is guard
    assert node_failed(wrapper, _Guard)
    assert not node_succeeded(wrapper, _Guard)


def test_node_lookup_missing_type_is_false():
    tree = _ran(_Fixed("Ok", Status.SUCCESS))
    assert find_node(tree, _Guard) is None
    assert not node_failed(tree, _Guard)
    assert not node_succeeded(tree, _Guard)


@pytest.mark.parametrize(
    "message",
    [
        "DataLayer not available",
        "DataLayer or actor_id not available",
        "trigger_activity_factory not available",
    ],
)
def test_missing_wiring_raises_rather_than_refusing(message):
    """A node that could not reach its DataLayer or a port reports a
    deployment fault, not the sender's error, so it is never REFUSED."""
    tree = _ran(_Fixed("NeedsPort", Status.FAILURE, message))
    with pytest.raises(VultronBTInternalError, match=message):
        verdict_from_bt(
            tree, BTExecutionResult(status=Status.FAILURE), label="TestBT"
        )


def test_node_failed_matches_any_node_of_the_type():
    """One node type can sit on several branches; a later one failing counts."""
    first = _Guard("First", Status.SUCCESS)
    second = _Guard("Second", Status.FAILURE)
    tree = _ran(first, second)
    assert node_failed(tree, _Guard)
    assert node_succeeded(tree, _Guard)


def test_find_named_locates_a_composite_by_name():
    arm = py_trees.composites.Sequence(name="Arm", memory=False)
    arm.add_child(_Fixed("Leaf", Status.SUCCESS))
    tree = _ran(arm)
    assert find_named(tree, "Arm") is arm
    assert find_named(tree, "Missing") is None


def test_applied_or_raise_raises_on_any_failure():
    """A store-only tree's failure is a local fault, never a refusal."""
    tree = _ran(_Fixed("Store", Status.FAILURE, "write failed"))
    with pytest.raises(VultronBTInternalError, match="write failed"):
        applied_or_raise(
            tree, BTExecutionResult(status=Status.FAILURE), label="TestBT"
        )


def test_applied_or_raise_passes_success_through():
    tree = _ran(_Fixed("Store", Status.SUCCESS))
    verdict = applied_or_raise(
        tree, BTExecutionResult(status=Status.SUCCESS), label="TestBT"
    )
    assert verdict.disposition == HandlerDisposition.APPLIED


# ---------------------------------------------------------------------------
# not_case_manager_refusal (HP-01-005, #3752)
# ---------------------------------------------------------------------------


_CASE_ID = "https://example.org/cases/gate-verdict"
_STORE_OWNER = "https://example.org/actors/store-owner"
_OTHER_MANAGER = "https://example.org/actors/other-manager"


def _store(
    holds_case: bool = True, manager_id: str | None = _OTHER_MANAGER
) -> SqliteDataLayer:
    """The store-owner's own store, holding (or not) the case.

    *manager_id* names who holds ``CVDRole.CASE_MANAGER`` on the case; ``None``
    seeds a case with no role holder at all.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_STORE_OWNER)
    if holds_case:
        case = as_VulnerabilityCase(id_=_CASE_ID, name="Gate verdict")
        if manager_id is not None:
            seed_case_manager_participant(dl, case, manager_id)
        dl.create(case)
    return dl


def _gated_run(gate_status: Status) -> py_trees.behaviour.Behaviour:
    """A tree whose CASE_MANAGER check reports *gate_status*.

    The check is the real node, so the helper's type lookup finds it; its
    status is set directly rather than ticked, since ticking needs the BT
    bridge's ports and store.
    """
    from vultron.core.behaviors.case.nodes.conditions import (
        CheckIsCaseManagerNode,
    )

    check = CheckIsCaseManagerNode(case_id=_CASE_ID)
    check.status = gate_status
    root = py_trees.composites.Selector(name="Root", memory=False)
    root.add_children(
        [
            py_trees.decorators.Inverter(name="Inv", child=check),
            _Fixed("Work", Status.SUCCESS),
        ]
    )
    return root


@pytest.mark.spec("HP-01-005")
def test_not_case_manager_refusal_is_none_when_the_gate_passed():
    tree = _gated_run(Status.SUCCESS)
    assert not_case_manager_refusal(tree, _store(), _CASE_ID) is None


@pytest.mark.spec("HP-01-005")
def test_not_case_manager_refusal_is_none_without_a_gate():
    tree = _ran(_Fixed("Ok", Status.SUCCESS))
    assert not_case_manager_refusal(tree, _store(), _CASE_ID) is None


@pytest.mark.spec("HP-01-005")
def test_not_case_manager_refusal_names_the_missing_role():
    """Somebody else holds CASE_MANAGER: this actor is not it."""
    tree = _gated_run(Status.FAILURE)
    verdict = not_case_manager_refusal(tree, _store(), _CASE_ID)
    assert verdict is not None
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == f"not the CASE_MANAGER of case '{_CASE_ID}'"


@pytest.mark.spec("HP-01-005")
def test_not_case_manager_refusal_names_the_unknown_case():
    tree = _gated_run(Status.FAILURE)
    verdict = not_case_manager_refusal(
        tree, _store(holds_case=False), _CASE_ID
    )
    assert verdict is not None
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == f"unknown case '{_CASE_ID}'"


@pytest.mark.spec("HP-01-005")
def test_not_case_manager_refusal_names_a_case_with_no_manager():
    """The gate also fails when no participant holds the role at all.

    That is a distinct state from "somebody else is the manager", and the
    reason says which, because at such a case nobody can pass the gate
    (CM-02-014, CM-02-015).
    """
    tree = _gated_run(Status.FAILURE)
    verdict = not_case_manager_refusal(tree, _store(manager_id=None), _CASE_ID)
    assert verdict is not None
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == f"case '{_CASE_ID}' has no CASE_MANAGER"
