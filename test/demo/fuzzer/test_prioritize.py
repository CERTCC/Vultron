"""Tests for vultron.demo.fuzzer.report_management.prioritize."""

import pytest
import py_trees

from vultron.demo.fuzzer.base import (
    AlmostAlwaysSucceed,
    AlwaysSucceed,
    ProbablySucceed,
    UsuallySucceed,
)
from vultron.demo.fuzzer.report_management.prioritize import (
    EnoughPrioritizationInfo,
    GatherPrioritizationInfo,
    NoNewPrioritizationInfo,
    OnAccept,
    OnDefer,
)

_ALL_NODES = [
    NoNewPrioritizationInfo,
    EnoughPrioritizationInfo,
    GatherPrioritizationInfo,
    OnAccept,
    OnDefer,
]


@pytest.mark.parametrize("node_cls", _ALL_NODES)
def test_node_is_behaviour(node_cls):
    """Each node must be a py_trees Behaviour."""
    node = node_cls()
    assert isinstance(node, py_trees.behaviour.Behaviour)


@pytest.mark.parametrize("node_cls", _ALL_NODES)
def test_node_has_docstring(node_cls):
    """Each node must have a non-empty docstring (BT-16-003)."""
    assert node_cls.__doc__ and node_cls.__doc__.strip()


@pytest.mark.parametrize("node_cls", _ALL_NODES)
def test_node_name_defaults_to_class_name(node_cls):
    """Default name must be the class name."""
    node = node_cls()
    assert node.name == node_cls.__name__


@pytest.mark.parametrize("node_cls", _ALL_NODES)
def test_node_name_custom(node_cls):
    """Custom name must be respected."""
    node = node_cls(name="custom")
    assert node.name == "custom"


@pytest.mark.parametrize("node_cls", _ALL_NODES)
def test_update_returns_status(node_cls):
    """update() must return a valid py_trees Status."""
    node = node_cls()
    node.setup()
    status = node.update()
    assert status in (
        py_trees.common.Status.SUCCESS,
        py_trees.common.Status.FAILURE,
        py_trees.common.Status.RUNNING,
    )


def test_no_new_prioritization_info_base_type():
    assert issubclass(NoNewPrioritizationInfo, ProbablySucceed)


def test_enough_prioritization_info_base_type():
    assert issubclass(EnoughPrioritizationInfo, UsuallySucceed)


def test_gather_prioritization_info_base_type():
    assert issubclass(GatherPrioritizationInfo, AlmostAlwaysSucceed)


def test_on_accept_base_type():
    assert issubclass(OnAccept, AlwaysSucceed)


def test_on_defer_base_type():
    assert issubclass(OnDefer, AlwaysSucceed)


def test_no_new_prioritization_info_success_rate():
    assert NoNewPrioritizationInfo.success_rate == pytest.approx(2 / 3)


def test_enough_prioritization_info_success_rate():
    assert EnoughPrioritizationInfo.success_rate == pytest.approx(0.75)


def test_gather_prioritization_info_success_rate():
    assert GatherPrioritizationInfo.success_rate == pytest.approx(0.9)


def test_on_accept_always_succeeds():
    node = OnAccept()
    node.setup()
    assert node.update() == py_trees.common.Status.SUCCESS


def test_on_defer_always_succeeds():
    node = OnDefer()
    node.setup()
    assert node.update() == py_trees.common.Status.SUCCESS
