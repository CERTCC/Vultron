"""Tests for vultron.demo.fuzzer.report_management.validate."""

import pytest
import py_trees

from vultron.demo.fuzzer.base import (
    AlmostAlwaysSucceed,
    ProbablySucceed,
    UsuallySucceed,
)
from vultron.demo.fuzzer.report_management.validate import (
    EnoughValidationInfo,
    EvaluateReportCredibility,
    EvaluateReportValidity,
    GatherValidationInfo,
    NoNewValidationInfo,
)

_ALL_NODES = [
    NoNewValidationInfo,
    EvaluateReportCredibility,
    EvaluateReportValidity,
    EnoughValidationInfo,
    GatherValidationInfo,
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


def test_no_new_validation_info_base_type():
    assert issubclass(NoNewValidationInfo, ProbablySucceed)


def test_evaluate_report_credibility_base_type():
    assert issubclass(EvaluateReportCredibility, AlmostAlwaysSucceed)


def test_evaluate_report_validity_base_type():
    assert issubclass(EvaluateReportValidity, AlmostAlwaysSucceed)


def test_enough_validation_info_base_type():
    assert issubclass(EnoughValidationInfo, UsuallySucceed)


def test_gather_validation_info_base_type():
    assert issubclass(GatherValidationInfo, AlmostAlwaysSucceed)


def test_no_new_validation_info_success_rate():
    assert NoNewValidationInfo.success_rate == pytest.approx(2 / 3)


def test_evaluate_report_credibility_success_rate():
    assert EvaluateReportCredibility.success_rate == pytest.approx(0.9)


def test_evaluate_report_validity_success_rate():
    assert EvaluateReportValidity.success_rate == pytest.approx(0.9)


def test_enough_validation_info_success_rate():
    assert EnoughValidationInfo.success_rate == pytest.approx(0.75)


def test_gather_validation_info_success_rate():
    assert GatherValidationInfo.success_rate == pytest.approx(0.9)
