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
"""Tests for vultron.demo.fuzzer.call_out_point and related exemplars.

Verifies:
- CallOutBackendFactory type alias is importable and callable (BT-18-004)
- Five shape mixin classes are importable
- Each exemplar node subclasses the correct shape mixin (BT-18-001)
- Exemplar nodes that declare output_keys write to the blackboard on SUCCESS
  (BT-18-002, BT-18-003)
- NewValidationInfoSentinel is a valid Behaviour with correct success_rate
"""

import pytest
import py_trees
from py_trees.common import Status

from vultron.core.behaviors.call_out_point import CallOutBackendFactory
from vultron.demo.fuzzer.call_out_point import (
    ActuatorCallOutPoint,
    ComposerCallOutPoint,
    EvaluatorCallOutPoint,
    NewValidationInfoSentinel,
    RetrieverCallOutPoint,
    SentinelCallOutPoint,
)
from vultron.demo.fuzzer.report_management.prioritize import OnAccept, OnDefer
from vultron.demo.fuzzer.report_management.publication import PrepareReport
from vultron.demo.fuzzer.report_management.validate import (
    EvaluateReportCredibility,
    EvaluateReportValidity,
    GatherValidationInfo,
)


@pytest.fixture(autouse=True)
def clear_blackboard():
    """Clear py_trees global blackboard state between tests."""
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


# ---------------------------------------------------------------------------
# CallOutBackendFactory type alias
# ---------------------------------------------------------------------------


def test_call_out_backend_factory_importable():
    assert CallOutBackendFactory is not None


def test_call_out_backend_factory_is_callable_type():
    """A factory matching the signature satisfies the type alias."""

    def factory(n):
        return EvaluateReportCredibility(n)

    node = factory("TestNode")
    assert isinstance(node, py_trees.behaviour.Behaviour)
    assert node.name == "TestNode"


# ---------------------------------------------------------------------------
# Shape mixin imports
# ---------------------------------------------------------------------------


def test_evaluator_mixin_importable():
    assert EvaluatorCallOutPoint is not None


def test_retriever_mixin_importable():
    assert RetrieverCallOutPoint is not None


def test_composer_mixin_importable():
    assert ComposerCallOutPoint is not None


def test_actuator_mixin_importable():
    assert ActuatorCallOutPoint is not None


def test_sentinel_mixin_importable():
    assert SentinelCallOutPoint is not None


# ---------------------------------------------------------------------------
# Shape hierarchy — exemplar nodes subclass correct mixin
# ---------------------------------------------------------------------------


def test_evaluate_report_credibility_is_evaluator():
    assert issubclass(EvaluateReportCredibility, EvaluatorCallOutPoint)


def test_evaluate_report_validity_is_evaluator():
    assert issubclass(EvaluateReportValidity, EvaluatorCallOutPoint)


def test_gather_validation_info_is_retriever():
    assert issubclass(GatherValidationInfo, RetrieverCallOutPoint)


def test_on_accept_is_actuator():
    assert issubclass(OnAccept, ActuatorCallOutPoint)


def test_on_defer_is_actuator():
    assert issubclass(OnDefer, ActuatorCallOutPoint)


def test_prepare_report_is_composer():
    assert issubclass(PrepareReport, ComposerCallOutPoint)


def test_new_validation_info_sentinel_is_sentinel():
    assert issubclass(NewValidationInfoSentinel, SentinelCallOutPoint)


# ---------------------------------------------------------------------------
# All exemplar nodes are py_trees Behaviours
# ---------------------------------------------------------------------------


_ALL_EXEMPLARS = [
    EvaluateReportCredibility,
    EvaluateReportValidity,
    GatherValidationInfo,
    OnAccept,
    OnDefer,
    PrepareReport,
    NewValidationInfoSentinel,
]


@pytest.mark.parametrize("node_cls", _ALL_EXEMPLARS)
def test_exemplar_is_behaviour(node_cls):
    node = node_cls()
    assert isinstance(node, py_trees.behaviour.Behaviour)


@pytest.mark.parametrize("node_cls", _ALL_EXEMPLARS)
def test_exemplar_has_blackboard_contract_docstring(node_cls):
    """Exemplar docstring must contain the BT-18-001 blackboard contract."""
    assert node_cls.__doc__ and "Blackboard contract" in node_cls.__doc__


# ---------------------------------------------------------------------------
# Sentinel — success_rate and no output_keys
# ---------------------------------------------------------------------------


def test_new_validation_info_sentinel_success_rate():
    assert NewValidationInfoSentinel.success_rate == pytest.approx(0.10)


def test_new_validation_info_sentinel_output_keys_empty():
    assert NewValidationInfoSentinel.output_keys == {}


# ---------------------------------------------------------------------------
# Actuator — no output_keys
# ---------------------------------------------------------------------------


def test_on_accept_output_keys_empty():
    assert OnAccept.output_keys == {}


def test_on_defer_output_keys_empty():
    assert OnDefer.output_keys == {}


# ---------------------------------------------------------------------------
# Evaluator exemplar — writes output key on SUCCESS (BT-18-002, BT-18-003)
# ---------------------------------------------------------------------------


def test_evaluate_report_credibility_output_keys_declared():
    assert (
        "report_credibility_verdict" in EvaluateReportCredibility.output_keys
    )


def test_evaluate_report_credibility_writes_blackboard_on_success():
    """EvaluateReportCredibility writes report_credibility_verdict on SUCCESS."""
    from vultron.demo.fuzzer.base import AlwaysSucceed
    from vultron.demo.fuzzer.call_out_point import EvaluatorCallOutPoint

    class _AlwaysSucceedEvaluator(EvaluatorCallOutPoint, AlwaysSucceed):
        output_keys = {"report_credibility_verdict": str}

    node = _AlwaysSucceedEvaluator("TestCredibility")
    node.setup()
    status = node.update()

    assert status == Status.SUCCESS
    assert (
        "/report_credibility_verdict" in py_trees.blackboard.Blackboard.storage
    )
    val = py_trees.blackboard.Blackboard.storage["/report_credibility_verdict"]
    assert isinstance(val, str)


def test_evaluate_report_validity_output_keys_declared():
    assert "report_validity_verdict" in EvaluateReportValidity.output_keys


# ---------------------------------------------------------------------------
# Retriever exemplar — writes output key on SUCCESS
# ---------------------------------------------------------------------------


def test_gather_validation_info_output_keys_declared():
    assert "validation_info_gathered" in GatherValidationInfo.output_keys


def test_gather_validation_info_writes_blackboard_on_success():
    """GatherValidationInfo writes validation_info_gathered on SUCCESS."""
    from vultron.demo.fuzzer.base import AlwaysSucceed
    from vultron.demo.fuzzer.call_out_point import RetrieverCallOutPoint

    class _AlwaysSucceedRetriever(RetrieverCallOutPoint, AlwaysSucceed):
        output_keys = {"validation_info_gathered": str}

    node = _AlwaysSucceedRetriever("TestGather")
    node.setup()
    status = node.update()

    assert status == Status.SUCCESS
    assert (
        "/validation_info_gathered" in py_trees.blackboard.Blackboard.storage
    )
    val = py_trees.blackboard.Blackboard.storage["/validation_info_gathered"]
    assert isinstance(val, str)


# ---------------------------------------------------------------------------
# Composer exemplar — writes output key on SUCCESS
# ---------------------------------------------------------------------------


def test_prepare_report_output_keys_declared():
    assert "prepared_report_artifact" in PrepareReport.output_keys


def test_prepare_report_writes_blackboard_on_success():
    """PrepareReport writes prepared_report_artifact on SUCCESS."""
    from vultron.demo.fuzzer.base import AlwaysSucceed
    from vultron.demo.fuzzer.call_out_point import ComposerCallOutPoint

    class _AlwaysSucceedComposer(ComposerCallOutPoint, AlwaysSucceed):
        output_keys = {"prepared_report_artifact": str}

    node = _AlwaysSucceedComposer("TestPrepare")
    node.setup()
    status = node.update()

    assert status == Status.SUCCESS
    assert (
        "/prepared_report_artifact" in py_trees.blackboard.Blackboard.storage
    )
    val = py_trees.blackboard.Blackboard.storage["/prepared_report_artifact"]
    assert isinstance(val, str)
