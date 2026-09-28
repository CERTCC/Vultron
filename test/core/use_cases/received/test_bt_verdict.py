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

from vultron.core.behaviors.bridge import BTExecutionResult
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
    failure_reason,
    find_named,
    find_node,
    node_failed,
    node_succeeded,
    verdict_from_bt,
)
from vultron.errors import VultronBTInternalError


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
